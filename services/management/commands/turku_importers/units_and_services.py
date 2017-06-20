import random
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone

from services.models import Organization, OntologyTreeNode, Unit

from .organizations import ORGANIZATION_IDS
from .utils import ptv_get


def get_localized_values(data, data_type, field_name):
    ret = {}
    for datum in data:
        if datum['type'] != data_type:
            continue
        language = datum['language']
        ret['%s_%s' % (field_name, language)] = datum['value']
        if language == 'fi':
            ret[field_name] = datum['value']
    return ret


def get_location(data):
    for address in data['addresses']:
        lat = float(address['latitude']) if address['latitude'] else None
        lon = float(address['longitude']) if address['longitude'] else None

        if lat and lon:
            srid = 4326 if lat < 200 else 3047  # yes wonderful
            point = Point(lon, lat, srid=srid)
            if srid != 4326:
                point.transform(4326)
            return point

    print('could not find location, addresses %s' % data['addresses'])


def import_units_and_services():
    num_of_units = 0
    num_of_services = 0

    for organization in Organization.objects.filter(uuid__in=ORGANIZATION_IDS):
        units = Unit.objects.filter(organization=organization)
        OntologyTreeNode.objects.filter(units__in=units).delete()
        units.delete()

        url = 'ServiceChannel/organization/%s' % organization.uuid
        channels = ptv_get(url)

        for channel in channels:
            if channel['serviceChannelType'] != 'ServiceLocation':
                print('skipping service channel with type %s' % channel['serviceChannelType'])
                continue

            new_unit_data = {}
            location = get_location(channel)
            new_unit_data['location'] = location
            new_unit_data.update(
                get_localized_values(channel['serviceChannelNames'], 'Name', 'name')
            )
            new_unit_data.update(
                get_localized_values(channel['serviceChannelDescriptions'], 'Description', 'desc')
            )
            new_unit_data.update(
                get_localized_values(channel['serviceChannelDescriptions'], 'ShortDescription', 'short_desc')
            )
            new_unit_data['organization_id'] = organization.id
            new_unit_data['id'] = random.randint(1, 10000000)

            unit_obj = Unit.objects.create(**new_unit_data)
            num_of_units += 1

            url = 'Service/serviceChannel/%s' % channel['id']
            services = ptv_get(url)
            root_tree_nodes = []

            for service in services:
                new_service_data = {}
                new_service_data.update(
                    get_localized_values(service['serviceNames'], 'Name', 'name')
                )
                new_service_data['last_modified_time'] = timezone.now()
                new_service_data['id'] = random.randint(1, 10000000)
                service_obj, created = OntologyTreeNode.objects.get_or_create(
                    name=new_service_data['name'], defaults=new_service_data
                )
                if created:
                    num_of_services += 1
                unit_obj.service_tree_nodes.add(service_obj)
                service_obj.unit_count = service_obj.get_unit_count()
                service_obj.save()
                root_tree_nodes.append(service_obj.id)
            unit_obj.root_ontologytreenodes = ','.join(map(str, root_tree_nodes))
            unit_obj.save()

    print('Done. Imported %d units and %d services.' % (num_of_units, num_of_services))
