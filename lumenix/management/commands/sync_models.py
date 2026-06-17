from django.core.management.base import BaseCommand

from lumenix.services.models_sync import sync_models


class Command(BaseCommand):
    help = "Sync models from /api/models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing model rows before syncing.",
        )

    def handle(self, *args, **opts):
        result = sync_models(reset=opts["reset"])
        self.stdout.write(self.style.SUCCESS(f"Models sync: {result}"))
