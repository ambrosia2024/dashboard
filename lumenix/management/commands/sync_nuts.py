from django.core.management.base import BaseCommand

from lumenix.services.nuts_sync import sync_nuts


class Command(BaseCommand):
    help = "Sync NUTS regions by level (0/1/2/3) from SCiO API."

    def add_arguments(self, parser):
        parser.add_argument("--level", choices=["0", "1", "2", "3", "all"], default="all")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing rows for selected level(s) before syncing.",
        )

    def handle(self, *args, **opts):
        levels = [0, 1, 2, 3] if opts["level"] == "all" else [int(opts["level"])]

        totals = {"created": 0, "updated": 0, "unchanged": 0, "fetched": 0}
        for level in levels:
            res = sync_nuts(level=level, reset=opts["reset"])
            self.stdout.write(self.style.SUCCESS(f"NUTS L{level}: {res}"))
            for k in totals:
                totals[k] += res[k]
        self.stdout.write(self.style.SUCCESS(f"NUTS total: {totals}"))
