# lumenix/management/commands/sync_vocabulary.py

from django.core.management.base import BaseCommand, CommandError
from lumenix.services.vocabulary_sync import sync_vocabulary


class Command(BaseCommand):
    help = "Sync Ambrosia vocabularies (plants/pathogens). Use --vocab=plants|pathogens|all."

    def add_arguments(self, parser):
        parser.add_argument("--vocab", choices=["plants", "pathogens", "all"], default="all")

    def handle(self, *args, **opts):
        targets = ["plants", "pathogens"] if opts["vocab"] == "all" else [opts["vocab"]]
        totals = {"created": 0, "updated": 0, "unchanged": 0}
        for v in targets:
            res = sync_vocabulary(v)
            self.stdout.write(self.style.SUCCESS(f"{v}: {res}"))
            for k in totals:
                totals[k] += res[k]
        self.stdout.write(self.style.SUCCESS(f"Total: {totals}"))
