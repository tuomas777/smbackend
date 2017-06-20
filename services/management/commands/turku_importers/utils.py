import requests

URL_BASE = 'https://api.palvelutietovaranto.suomi.fi/api/v6/'


def ptv_get(url):
    full_url = "%s%s/" % (URL_BASE, url)
    print("CALLING URL >>> ", full_url)
    resp = requests.get(full_url)
    assert resp.status_code == 200, 'fuu status code {}'.format(resp.status_code)
    return resp.json()
