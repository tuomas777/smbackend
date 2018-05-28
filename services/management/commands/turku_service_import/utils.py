import datetime
import hashlib
import os

import requests
from django.conf import settings

from services.management.commands.utils.text import clean_text

# TODO: Change to production endpoint when available
TURKU_BASE_URL = 'https://testidigiaurajoki.turku.fi/kuntapalvelut/api/v1/'
ACCESSIBILITY_BASE_URL = 'https://asiointi.hel.fi/kapaesteettomyys_testi/api/v1/'


def get_resource(url, headers=None):
    print("CALLING URL >>> ", url)
    resp = requests.get(url, headers=headers)
    assert resp.status_code == 200, 'status code {}'.format(resp.status_code)
    return resp.json()


def get_turku_api_headers(content=''):
    application = 'Palvelukartta'
    key = getattr(settings, 'TURKU_API_KEY', '')
    now = datetime.datetime.utcnow()
    timestamp = now.strftime('%Y-%m-%dT%H:%M:%SZ')

    data = (application + timestamp + content + key).encode('utf-8')
    auth = hashlib.sha256(data)
    return {
        'Authorization': auth.hexdigest(),
        'X-TURKU-SP': application,
        'X-TURKU-TS': timestamp
    }


def get_ar_resource(resource_name):
    url = "{}{}".format(ACCESSIBILITY_BASE_URL, resource_name)
    return get_resource(url)


def get_ar_servicepoint_resource(resource_name=None):
    template_vars = [ACCESSIBILITY_BASE_URL, getattr(settings, 'ACCESSIBILITY_SYSTEM_ID', '')]
    url_template = "{}servicepoints/{}"
    if resource_name:
        template_vars.append(resource_name)
        url_template += '/{}'

    url = url_template.format(*template_vars)
    return get_resource(url)

def get_ar_servicepoint_accessibility_resource(resource_name=None):
    template_vars = [ACCESSIBILITY_BASE_URL, getattr(settings, 'ACCESSIBILITY_SYSTEM_ID', '')]
    url_template = "{}accessibility/servicepoints/{}"
    if resource_name:
        template_vars.append(resource_name)
        url_template += '/{}'

    url = url_template.format(*template_vars)
    return get_resource(url)


def get_turku_resource(resource_name):
    url = "{}{}".format(TURKU_BASE_URL, resource_name)
    headers = get_turku_api_headers()
    return get_resource(url, headers)


def set_tku_translated_field(obj, obj_field_name, entry_data, max_length=None):
    if not entry_data:
        return False

    has_changed = False

    for language, raw_value in entry_data.items():
        value = clean_text(raw_value)

        if max_length and value and len(value) > max_length:
            value = None

        obj_key = '{}_{}'.format(obj_field_name, language)
        obj_value = getattr(obj, obj_key)

        if obj_value == value:
            continue

        has_changed = True
        setattr(obj, obj_key, value)

    if has_changed:
        obj._changed = True

    return has_changed


def set_field(obj, obj_field_name, entry_value):
    value = clean_text(entry_value)
    obj_value = getattr(obj, obj_field_name)

    if obj_value == value:
        return False

    setattr(obj, obj_field_name, value)
    return True


def set_syncher_object_field(obj, obj_field_name, value):
    obj._changed |= set_field(obj, obj_field_name, value)


def set_syncher_tku_translated_field(obj, obj_field_name, value, max_length=None):
    obj._changed |= set_tku_translated_field(obj, obj_field_name, value, max_length)


def postcodes():
    path = os.path.join(settings.BASE_DIR, 'data', 'fi', 'postcodes.txt')
    _postcodes = {}
    f = open(path, 'r', encoding='utf-8')
    for l in f.readlines():
        code, muni = l.split(',')
        _postcodes[code] = muni.strip()
    return _postcodes
