import datetime
import hashlib
import os
import re

import requests
from django.conf import settings

# TODO: Change to production endpoint when available
TURKU_BASE_URL = 'https://testidigiaurajoki.turku.fi/kuntapalvelut/api/v1/'

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


def get_turku_resource(resource_name):
    url = "{}{}".format(TURKU_BASE_URL, resource_name)
    headers = get_turku_api_headers()
    return get_resource(url, headers)


def set_field(obj, obj_field_name, entry, entry_field_name):
    entry_value = entry[entry_field_name]
    value = clean_text(entry_value)

    obj_value = getattr(obj, obj_field_name)

    if obj_value == value:
        return False

    setattr(obj, obj_field_name, entry_value)
    return True


def clean_text(text):
    if not isinstance(text, str):
        return text
    # remove consecutive whitespaces
    text = re.sub(r'\s\s+', ' ', text, re.U)
    # remove nil bytes
    text = text.replace('\u0000', ' ')
    text = text.replace("\r", "\n")
    text = text.replace('\r', "\n")
    text = text.replace('\\r', "\n")
    text = text.strip()
    if len(text) == 0:
        return None
    return text


def postcodes():
    path = os.path.join(settings.BASE_DIR, 'data', 'fi', 'postcodes.txt')
    _postcodes = {}
    f = open(path, 'r', encoding='utf-8')
    for l in f.readlines():
        code, muni = l.split(',')
        _postcodes[code] = muni.strip()
    return _postcodes
