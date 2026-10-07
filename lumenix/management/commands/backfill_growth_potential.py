from django.core.management.base import BaseCommand, CommandError

from lumenix.models import PathogenQuerySpec
from lumenix.services.growth_potential import backfill


class Command(BaseCommand):
    help = (
        "Fill growth_potential_auc on existing pathogen records from their stored "
        "temperature, via the A(T) lookup. Chunked per group of regions, resumable "
        "(only NULL rows are touched)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--plant", default="")
        parser.add_argument("--pathogen", default="")

    def handle(self, *args, **opts):
        pairs = PathogenQuerySpec.objects.order_by().values_list("plant", "pathogen").distinct()
        if opts["plant"]:
            pairs = pairs.filter(plant=opts["plant"])
        if opts["pathogen"]:
            pairs = pairs.filter(pathogen=opts["pathogen"])
        pairs = list(pairs)
        if not pairs:
            raise CommandError("No matching crop + hazard pairs in the query specs.")

        for plant, pathogen in pairs:
            self.stdout.write(f"Backfilling {plant} x {pathogen}...")
            totals = backfill(plant, pathogen, log=self.stdout.write)
            style = self.style.SUCCESS if not totals["out_of_range"] else self.style.WARNING
            self.stdout.write(style(
                f"  updated {totals['updated']:,} rows | NaN temperature {totals['nan_temperature']:,} | "
                f"outside sampled range {totals['out_of_range']:,} | still NULL {totals['still_null']:,}"
            ))
