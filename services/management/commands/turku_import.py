# -*- coding: utf-8 -*-
import sys
import pytz
from django.core.management.base import BaseCommand
from django import db
from django.conf import settings
from django.utils.translation import activate, get_language

from .turku_importers import import_addresses, import_organizations, import_units_and_services

UTC_TIMEZONE = pytz.timezone('UTC')


class Command(BaseCommand):
    help = "Import Turku data"
    importer_types = ['organizations', 'units_and_services', 'addresses']

    def __init__(self):
        super(Command, self).__init__()
        self.options = {}
        for imp in self.importer_types:
            method = "import_%s" % imp
            assert getattr(self, method, False), "No importer defined for %s" % method

    def add_arguments(self, parser):
        parser.add_argument('import_types', nargs='*', choices=self.importer_types)

    @db.transaction.atomic
    def import_organizations(self):
        return import_organizations()

    @db.transaction.atomic
    def import_units_and_services(self):
        import_units_and_services()

    @db.transaction.atomic
    def import_addresses(self):
        import_addresses()

    def handle(self, **options):
        self.options = options

        # Activate the default language for the duration of the import
        # to make sure translated fields are populated correctly.
        old_lang = get_language()
        activate(settings.LANGUAGES[0][0])

        import_count = 0
        for imp in self.importer_types:
            if imp not in options["import_types"]:
                continue
            method = getattr(self, "import_%s" % imp)
            print("Importing %s..." % imp)
            method()
            import_count += 1

        if not import_count:
            sys.stderr.write("Nothing to import.\n")
        activate(old_lang)
