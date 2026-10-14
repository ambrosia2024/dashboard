from django.core.management.base import BaseCommand, CommandError

from lumenix.services.cardinal_growth import INDICES, build_monthly


class Command(BaseCommand):
    help = (
        "Compute the monthly cardinal-model (Rosso 1993) growth response per region "
        "from the daily temperatures on the pathogen records, for the month and year "
        "steps of the Europe growth map. Re-run after a pathogen sync or after "
        "changing an index's cardinal temperatures."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--index", action="append", choices=sorted(INDICES),
            help="Index to build (repeatable). Default: all.",
        )
        parser.add_argument("--chunk-regions", type=int, default=20)

    def handle(self, *args, **opts):
        keys = opts["index"] or sorted(INDICES)
        if opts["chunk_regions"] < 1:
            raise CommandError("--chunk-regions must be at least 1.")
        for key in keys:
            index = INDICES[key]
            self.stdout.write(
                f"Building {index.label} (Tmin {index.t_min:g}, Topt {index.t_opt:g}, Tmax {index.t_max:g} °C)..."
            )
            totals = build_monthly(index, chunk_regions=opts["chunk_regions"], log=self.stdout.write)
            self.stdout.write(self.style.SUCCESS(
                f"  {totals['rows']:,} monthly rows for {totals['regions']} regions"
            ))
