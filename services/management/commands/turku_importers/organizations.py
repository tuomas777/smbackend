from munigeo.importer.sync import ModelSyncher
from services.models import Organization
from .utils import ptv_get

URL_BASE = 'https://api.palvelutietovaranto.suomi.fi/api/v6/'
ORGANIZATION_IDS = ['fbf1b51b-5378-459f-8b44-e502d222e13f']


def import_organizations():
    obj_list = []
    for org_id in ORGANIZATION_IDS:
        obj_list.append(ptv_get('organization/%s' % org_id))

    syncher = ModelSyncher(Organization.objects.all(), lambda obj: str(obj.uuid))

    for data in obj_list:
        obj = syncher.get(data['id'])
        obj_has_changed = False
        if not obj:
            obj = Organization(uuid=data['id'])
            obj_has_changed = True

        new_org_data = {}
        new_org_data['business_id'] = data['businessCode']
        new_org_data['organization_type'] = data['organizationType']
        new_org_data['municipality_code'] = data['municipality']['code']
        new_org_data['oid'] = data['oid']

        for org_name in data['organizationNames']:
            if org_name['type'] != 'Name':
                continue
            new_org_data['name_%s' % org_name['language']] = org_name['value']

        obj.uuid = data['id']

        for field in new_org_data.keys():
            if getattr(obj, field) != new_org_data[field]:
                obj_has_changed = True
                setattr(obj, field, new_org_data.get(field))

        if obj_has_changed:
            obj.save()
        syncher.mark(obj)

    syncher.finish()
    return syncher

