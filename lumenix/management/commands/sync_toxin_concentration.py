from django.core.management.base import BaseCommand, CommandError

from lumenix.models import ToxinQuerySpec
from lumenix.services.toxin_query import sync_toxin_query_spec


class Command(BaseCommand):
    help = "Sync configured toxin concentration datasets from SCiO."

    def add_arguments(self, parser):
        parser.add_argument("--spec-id", type=int, help="Sync only one ToxinQuerySpec by id.")
        parser.add_argument("--all", action="store_true", help="Sync all active toxin query specs.")

    def handle(self, *args, **options):
        spec_id = options.get("spec_id")
        sync_all = options.get("all")

        if not spec_id and not sync_all:
            raise CommandError("Provide --spec-id <id> or --all.")

        if spec_id:
            specs = ToxinQuerySpec.active_objects.filter(pk=spec_id)
        else:
            specs = ToxinQuerySpec.active_objects.all()

        if not specs.exists():
            raise CommandError("No matching active toxin query specs found.")

        for spec in specs:
            res = sync_toxin_query_spec(spec)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{spec.name}: created={res['created']}, updated={res['updated']}, "
                    f"unchanged={res['unchanged']}, fetched={res['fetched']}"
                )
            )

