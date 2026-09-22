from django.db import migrations, models

# Drops the two JSON columns that made up ~94% of pathogen_concentration_records
# (the per-day model curve and a copy of the raw API item; nothing read them) and
# the single-column indexes made redundant by the composite unique constraint.
#
# Dropping a column in PostgreSQL is instant, but the space is only returned to
# the disk after `VACUUM FULL pathogen_concentration_records;` (see the deploy
# runbook) — run that once per environment when there is free disk for the
# rewritten copy (~10% of the current table size).


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0042_guidance_future_badge"),
    ]

    operations = [
        migrations.RemoveField(model_name="pathogenconcentrationrecord", name="outcome"),
        migrations.RemoveField(model_name="pathogenconcentrationrecord", name="source_payload"),
        migrations.AlterField(model_name="pathogenconcentrationrecord", name="plant", field=models.SlugField(max_length=100)),
        migrations.AlterField(model_name="pathogenconcentrationrecord", name="pathogen", field=models.SlugField(max_length=100)),
        migrations.AlterField(model_name="pathogenconcentrationrecord", name="nuts_code", field=models.CharField(max_length=32)),
    ]
