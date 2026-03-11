from django.core.management.base import BaseCommand

from lumenix.services.models_sync import sync_models


class Command(BaseCommand):
    help = "Sync SCiO models from /api/models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing SCiO model rows before syncing.",
        )

    def handle(self, *args, **opts):
        result = sync_models(reset=opts["reset"])
        self.stdout.write(self.style.SUCCESS(f"SCiO models sync: {result}"))
