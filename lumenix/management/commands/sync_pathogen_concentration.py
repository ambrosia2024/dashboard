from django.core.management.base import BaseCommand, CommandError

from lumenix.models import PathogenQuerySpec
from lumenix.services.pathogen_query import sync_pathogen_query_spec


class Command(BaseCommand):
    help = "Sync configured pathogen concentration datasets from the source API."

    def add_arguments(self, parser):
        parser.add_argument("--spec-id", type=int, help="Sync only one pathogen query spec by id.")
        parser.add_argument("--all", action="store_true", help="Sync all active pathogen query specs.")

    def handle(self, *args, **options):
        spec_id = options.get("spec_id")
        sync_all = options.get("all")

        if not spec_id and not sync_all:
            raise CommandError("Provide --spec-id <id> or --all.")

        if spec_id:
            specs = PathogenQuerySpec.active_objects.filter(pk=spec_id)
        else:
            specs = PathogenQuerySpec.active_objects.all()

        if not specs.exists():
            raise CommandError("No matching active pathogen query specs found.")

        for spec in specs:
            res = sync_pathogen_query_spec(spec)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{spec.name}: created={res['created']}, updated={res['updated']}, "
                    f"unchanged={res['unchanged']}, fetched={res['fetched']}"
                )
            )

