import json
from datetime import datetime

import pytz
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from munigeo.importer.sync import ModelSyncher

from services.management.commands.services_import.services import update_service_node_counts
from services.management.commands.turku_service_import.utils import set_syncher_object_field, \
    set_syncher_tku_translated_field, get_turku_resource
from services.management.commands.utils.text import clean_text
from services.models import Service, ServiceNode, Unit, UnitServiceDetails, UnitIdentifier

UTC_TIMEZONE = pytz.timezone('UTC')

ROOT_FIELD_MAPPING = {
    'nimi_kieliversiot': 'name',
    'kuvaus_kieliversiot': 'description',
    'sahkoposti': 'email',
}

EXTRA_INFO_FIELD_MAPPING = {
    '6': {'kuvaus_kieliversiot': 'www'},
}

SERVICE_TRANSLATIONS = {
    'fi': 'Palvelut',
    'sv': 'Tjänster',
    'en': 'Services'
}

SOURCE_DATA_SRID = 4326

BOUNDING_BOX = Polygon.from_bbox(settings.BOUNDING_BOX)
BOUNDING_BOX.set_srid(settings.DEFAULT_SRID)
BOUNDING_BOX.transform(SOURCE_DATA_SRID)


class UnitImporter:
    unitsyncher = ModelSyncher(Unit.objects.all(), lambda obj: obj.id)

    def __init__(self, logger=None, importer=None):
        self.logger = logger
        self.importer = importer

    def import_units(self):
        units = get_turku_resource('palvelupisteet')

        for unit in units:
            self._handle_unit(unit)

        self.unitsyncher.finish()

        update_service_node_counts()

    def _handle_unit(self, unit_data):
        unit_id = int(unit_data['koodi'])
        state = unit_data['tila'].get('koodi')

        if state != '1':
            self.logger.debug('Skipping service point "{}" state "{}".'.format(unit_id, state))
            return

        obj = self.unitsyncher.get(unit_id)
        if not obj:
            obj = Unit(id=unit_id)
            obj._changed = True

        self._handle_root_fields(obj, unit_data)
        self._handle_location(obj, unit_data)
        self._handle_extra_info(obj, unit_data)
        self._handle_ptv_id(obj, unit_data)
        self._handle_service_descriptions(obj, unit_data)
        self._save_object(obj)

        self._handle_services_and_service_nodes(obj, unit_data)
        self._save_object(obj)

        self.unitsyncher.mark(obj)

    def _save_object(self, obj):
        if obj._changed:
            obj.last_modified_time = datetime.now(UTC_TIMEZONE)
            obj.save()
            if self.importer:
                self.importer.services_changed = True

    def _handle_root_fields(self, obj, unit_data):
        self._update_fields(obj, unit_data, ROOT_FIELD_MAPPING)

    def _handle_location(self, obj, unit_data):
        location_data = unit_data.get('fyysinenPaikka')
        location = None

        if location_data:
            latitude = location_data.get('leveysaste')
            longitude = location_data.get('pituusaste')

            if latitude and longitude:
                point = Point(float(longitude), float(latitude), srid=SOURCE_DATA_SRID)

                if point.within(BOUNDING_BOX):
                    point.transform(settings.DEFAULT_SRID)
                    location = point

        set_syncher_object_field(obj, 'location', location)

        if not location_data:
            return

        address_data_list = location_data.get('osoitteet')

        if address_data_list:
            # TODO what if there are multiple addresses
            address_data = address_data_list[0]

            full_postal_address = {}

            street_fi = address_data.get('katuosoite_fi')
            zip = address_data.get('postinumero')
            post_office_fi = address_data.get('postitoimipaikka_fi')
            full_postal_address['fi'] = '{} {} {}'.format(street_fi, zip, post_office_fi)

            for language in ('sv', 'en'):
                street = address_data.get('katuosoite_{}'.format(language)) or street_fi
                post_office = address_data.get('postitoimipaikka_{}'.format(language)) or post_office_fi
                full_postal_address[language] = '{} {} {}'.format(street, zip, post_office)

            set_syncher_tku_translated_field(obj, 'address_postal_full', full_postal_address)

    def _handle_extra_info(self, obj, unit_data):
        # TODO handle existing extra data erasing when needed

        location_data = unit_data.get('fyysinenPaikka')
        if not location_data:
            return

        for extra_info_data in location_data.get('lisatiedot', []):
            try:
                koodi = extra_info_data['lisatietotyyppi'].get('koodi')
                field_mapping = EXTRA_INFO_FIELD_MAPPING[koodi]
            except KeyError:
                continue
            self._update_fields(obj, extra_info_data, field_mapping)

    def _handle_ptv_id(self, obj, unit_data):
        ptv_id = unit_data.get('ptv_id')

        if ptv_id:
            created, _ = UnitIdentifier.objects.get_or_create(namespace='ptv', value=ptv_id, unit=obj)
            if created:
                obj._changed = True
        else:
            num_of_deleted, _ = UnitIdentifier.objects.filter(namespace='ptv', unit=obj).delete()
            if num_of_deleted:
                obj._changed = True

    def _handle_services_and_service_nodes(self, obj, unit_data):
        old_service_ids = set(obj.services.values_list('id', flat=True))
        old_service_node_ids = set(obj.service_nodes.values_list('id', flat=True))
        obj.services.clear()
        obj.service_nodes.clear()

        for service_offer in unit_data.get('palvelutarjoukset', []):
            for service_data in service_offer.get('palvelut', []):
                service_id = int(service_data.get('koodi'))
                try:
                    service = Service.objects.get(id=service_id)
                except Service.DoesNotExist:
                    # TODO fail the unit node completely here?
                    self.logger.warning('Service "{}" does not exist!'.format(service_id))
                    continue

                UnitServiceDetails.objects.get_or_create(unit=obj, service=service)

                service_nodes = ServiceNode.objects.filter(related_services=service)
                obj.service_nodes.add(*service_nodes)

        new_service_ids = set(obj.services.values_list('id', flat=True))
        new_service_node_ids = set(obj.service_nodes.values_list('id', flat=True))

        if old_service_ids != new_service_ids or old_service_node_ids != new_service_node_ids:
            obj._changed = True

        set_syncher_object_field(obj, 'root_service_nodes', ','.join(str(x) for x in obj.get_root_service_nodes()))

    def _handle_service_descriptions(self, obj, unit_data):
        description_data = unit_data.get('kuvaus_kieliversiot', {})
        descriptions = {lang: description_data.get(lang, '') for lang in ('fi', 'sv', 'en')}
        touched = {
            'fi': False,
            'sv': False,
            'en': False,
        }

        for service_offer in unit_data.get('palvelutarjoukset', []):
            for service_data in service_offer.get('palvelut', []):

                service_name = service_data.get('nimi_kieliversiot', {})
                for language, value in service_name.items():
                    # Make sure that we have a string as the default value
                    if not descriptions[language]:
                        descriptions[language] = ''

                    if not touched[language]:
                        # Clean the text
                        descriptions[language] = clean_text(descriptions[language], '')
                        # Add some padding if there is a description already
                        if descriptions[language]:
                            descriptions[language] += '\n\n'
                        descriptions[language] += SERVICE_TRANSLATIONS[language] + ':\n'
                    else:
                        # Add newline between services
                        descriptions[language] += '\n'

                    descriptions[language] += '- ' + value
                    touched[language] = True

        set_syncher_tku_translated_field(obj, 'description', descriptions, clean=False)

    @staticmethod
    def _update_fields(obj, imported_data, field_mapping):
        for data_field, model_field in field_mapping.items():
            value = imported_data.get(data_field)

            if data_field.endswith('_kieliversiot'):
                set_syncher_tku_translated_field(obj, model_field, value)
            else:
                set_syncher_object_field(obj, model_field, value)


def import_units(**kwargs):
    unit_importer = UnitImporter(**kwargs)
    return unit_importer.import_units()
