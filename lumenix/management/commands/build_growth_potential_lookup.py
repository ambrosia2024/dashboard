from django.core.management.base import BaseCommand, CommandError

from lumenix.models import PathogenQuerySpec
from lumenix.services.growth_potential import (
    DEFAULT_PROBES, DEFAULT_T_EVAL_HOURS, build_lookup, extend_lookup,
)


class Command(BaseCommand):
    help = (
        "Build the A(T) growth-potential lookup for each synced crop + hazard pair "
        "by sampling the source API across cold-to-hot probe regions."
    )

    def add_arguments(self, parser):
        parser.add_argument("--plant", default="", help="Limit to one crop identifier.")
        parser.add_argument("--pathogen", default="", help="Limit to one hazard identifier.")
        parser.add_argument("--t-eval", type=float, default=DEFAULT_T_EVAL_HOURS,
                            help=f"Evaluation window in hours (default {DEFAULT_T_EVAL_HOURS:g}).")
        parser.add_argument("--extend", action="store_true",
                            help="Widen the existing lookup by sampling only the region-years "
                                 "whose stored temperatures fall outside its current range.")

    def handle(self, *args, **opts):
        pairs = (
            PathogenQuerySpec.objects.order_by().values_list("plant", "pathogen").distinct()
        )
        if opts["plant"]:
            pairs = pairs.filter(plant=opts["plant"])
        if opts["pathogen"]:
            pairs = pairs.filter(pathogen=opts["pathogen"])
        pairs = list(pairs)
        if not pairs:
            raise CommandError("No matching crop + hazard pairs in the query specs.")

        for plant, pathogen in pairs:
            if opts["extend"]:
                lookup, probed = extend_lookup(plant, pathogen)
                if not probed:
                    self.stdout.write(self.style.SUCCESS(f"  {lookup}: already covers every stored temperature."))
                    continue
                self.stdout.write(f"  extended via {probed} region-year window(s)")
            else:
                self.stdout.write(f"Sampling {plant} x {pathogen} over {len(DEFAULT_PROBES)} probes...")
                lookup = build_lookup(plant, pathogen, t_eval_hours=opts["t_eval"])
            self.stdout.write(self.style.SUCCESS(
                f"  {lookup}: T {lookup.t_min:.2f}..{lookup.t_max:.2f} C, y0={lookup.y0:g}, "
                f"horizon={lookup.horizon_hours:g}h"
            ))
            self.stdout.write(
                "  Records with temperatures outside this range stay NULL in a backfill; "
                "widen the probes if the backfill reports them."
            )
