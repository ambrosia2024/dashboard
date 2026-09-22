"""
Index for the region-first queries the admin and the charts actually run.

Built CONCURRENTLY: the table holds millions of rows in production, and a plain
CREATE INDEX would hold a lock on it for the whole build while the sync and the
dashboard wait. That requires the migration to run outside a transaction.
"""

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("lumenix", "0043_slim_pathogen_records"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="pathogenconcentrationrecord",
            index=models.Index(fields=["nuts_code", "-observed_on"], name="idx_pcr_region_observed"),
        ),
    ]
