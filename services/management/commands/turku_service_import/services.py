from datetime import datetime

import pytz
from munigeo.importer.sync import ModelSyncher

from services.management.commands.services_import.keyword import KeywordHandler
from services.management.commands.turku_service_import.utils import get_turku_resource, set_syncher_object_field, \
    set_syncher_tku_translated_field
from services.models import ServiceNode, Service

UTC_TIMEZONE = pytz.timezone('UTC')


class ServiceImporter:
    nodesyncher = ModelSyncher(ServiceNode.objects.all(), lambda obj: obj.ext_id)
    servicesyncher = ModelSyncher(Service.objects.all(), lambda obj: obj.id)

    def __init__(self, logger=None, importer=None):
        self.logger = logger
        self.importer = importer

    def import_services(self):
        keyword_handler = KeywordHandler(logger=self.logger)
        self._import_services(keyword_handler)
        self._import_service_nodes(keyword_handler)

    def _import_service_nodes(self, keyword_handler):
        service_classes = get_turku_resource('palveluluokat')
        tree = self._build_servicetree(service_classes)
        for parent_node in tree:
            latest_node_id = 0
            latest_node = ServiceNode.objects.order_by('id').last()
            if latest_node:
                latest_node_id = latest_node.id
            self._handle_service_node(parent_node, keyword_handler, latest_node_id)
        self.nodesyncher.finish()

    def _import_services(self, keyword_handler):
        services = get_turku_resource('palvelut')
        for service in services:
            self._handle_service(service, keyword_handler)
        self.servicesyncher.finish()

    def _save_object(self, obj):
        if obj._changed:
            obj.last_modified_time = datetime.now(UTC_TIMEZONE)
            obj.save()
            if self.importer:
                self.importer.services_changed = True

    def _build_servicetree(self, service_classes):
        tree = [s_cls for s_cls in service_classes if 'ylatason_koodi' not in s_cls]
        for parent in tree:
            self._add_service_tree_children(parent, service_classes)

        return tree

    def _add_service_tree_children(self, parent_classes, service_classes):
        parent_classes['children'] = [s_cls for s_cls in service_classes if
                                      s_cls.get('ylatason_koodi') == parent_classes['koodi']]

        for child_ot in parent_classes['children']:
            self._add_service_tree_children(child_ot, service_classes)

    def _handle_service_node(self, node, keyword_handler, latest_node_id):
        obj = self.nodesyncher.get(node['koodi'])
        if not obj:
            latest_node_id += 1
            obj = ServiceNode(
                id=latest_node_id,
                ext_id=node['koodi']
            )
            obj._changed = True

        name = node.get('nimi')
        set_syncher_object_field(obj, 'name', name)
        set_syncher_object_field(obj, 'name_fi', name)

        if 'ylatason_koodi' in node:
            parent = self.nodesyncher.get(node['ylatason_koodi'])
            assert parent
        else:
            parent = None
        if obj.parent != parent:
            obj.parent = parent
            obj._changed = True

        obj._changed |= self._update_object_unit_count(obj)
        self._save_object(obj)

        self._handle_related_services(obj, node)

        self.nodesyncher.mark(obj)

        for child_node in node['children']:
            latest_node_id = self._handle_service_node(child_node, keyword_handler, latest_node_id)

        return latest_node_id

    def _handle_related_services(self, obj, node):
        old_service_ids = set(obj.related_services.values_list('id', flat=True))
        obj.related_services.clear()

        for service_data in node.get('palvelut', []):
            service_id = int(service_data.get('koodi'))

            try:
                service = Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                # TODO fail the service node completely here?
                self.logger.warning('Service "{}" does not exist!'.format(service_id))
                continue

            obj.related_services.add(service)

        new_service_ids = set(obj.related_services.values_list('id', flat=True))

        if old_service_ids != new_service_ids:
            obj._changed = True

    def _update_object_unit_count(self, obj):
        unit_count = obj.get_unit_count()
        if obj.unit_count != unit_count:
            obj.unit_count = unit_count
            return True
        return False

    def _handle_service(self, service, keyword_handler):
        koodi = int(service['koodi'])  # Cast to int as koodi should always be a stringified integer
        obj = self.servicesyncher.get(koodi)
        if not obj:
            obj = Service(
                id=koodi,
                clarification_enabled=False,
                period_enabled=False
            )
            obj._changed = True

        set_syncher_tku_translated_field(obj, 'name', service.get('nimi_kieliversiot'))

        obj._changed = keyword_handler.sync_searchwords(obj, service, obj._changed)
        obj._changed |= self._update_object_unit_count(obj)

        self._save_object(obj)
        self.servicesyncher.mark(obj)


def import_services(**kwargs):
    service_importer = ServiceImporter(**kwargs)
    return service_importer.import_services()
