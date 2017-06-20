import csv
from django.contrib.gis.geos import Point, Polygon

from munigeo.models import Address, Municipality, Street


def import_addresses():
    Street.objects.all().delete()
    Address.objects.all().delete()
    turku = Municipality.objects.get(id='turku')
    i = 0

    with open('data/turku_poc/02addresses2017-05-15.csv', 'rt') as csvfile:
        address_reader = csv.DictReader(csvfile)
        for row in address_reader:
            if row['municipality'] != '853':  # Turku only
                continue

            street, _ = Street.objects.get_or_create(municipality=turku, name=row['street'])
            location = Point(
                float(row['longitude_wgs84']),
                float(row['latitude_wgs84']),
                srid=4326,
            )
            address, created = Address.objects.get_or_create(
                street=street,
                number=row['house_number'],
                defaults={'location': location}
            )

            i += 1
            print('row %d / ~42k' % i)

            if created:
                address.refresh_from_db()
                print('created address %s' % address)
