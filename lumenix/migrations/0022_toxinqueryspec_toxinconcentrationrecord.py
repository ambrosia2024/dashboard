from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0021_userprofile_dashboard_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="ToxinQuerySpec",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.SmallIntegerField(choices=[(1, "Active"), (0, "Inactive"), (2, "Deleted")], default=1, verbose_name="Status")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("plant", models.SlugField(help_text="SCiO plant identifier, e.g. 'lettuce'.", max_length=100)),
                ("pathogen", models.SlugField(help_text="SCiO pathogen identifier, e.g. 'salmonella'.", max_length=100)),
                ("nuts_code", models.CharField(help_text="NUTS code, e.g. 'AL' or 'NL42'.", max_length=32)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("time_scale", models.CharField(choices=[("daily", "Daily")], default="daily", max_length=20)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "toxin_query_specs",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ToxinConcentrationRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.SmallIntegerField(choices=[(1, "Active"), (0, "Inactive"), (2, "Deleted")], default=1, verbose_name="Status")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("plant", models.SlugField(db_index=True, max_length=100)),
                ("pathogen", models.SlugField(db_index=True, max_length=100)),
                ("nuts_code", models.CharField(db_index=True, max_length=32)),
                ("observed_on", models.DateField(db_index=True)),
                ("source_time", models.CharField(blank=True, default="", max_length=64)),
                ("source_period", models.CharField(blank=True, default="", max_length=64)),
                ("toxin_value", models.FloatField(blank=True, null=True)),
                ("temperature_c", models.FloatField(blank=True, null=True)),
                ("outcome", models.JSONField(blank=True, default=list)),
                ("provenance_model_id", models.CharField(blank=True, default="", max_length=128)),
                ("provenance_model_title", models.CharField(blank=True, default="", max_length=512)),
                ("provenance_variable_name", models.CharField(blank=True, default="", max_length=128)),
                ("provenance_fetched_at_ms", models.BigIntegerField(blank=True, null=True)),
                ("source_payload", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "toxin_concentration_records",
                "ordering": ["observed_on"],
            },
        ),
        migrations.AddConstraint(
            model_name="toxinqueryspec",
            constraint=models.UniqueConstraint(fields=("plant", "pathogen", "nuts_code", "start_date", "end_date", "time_scale"), name="uq_toxin_query_spec_scope"),
        ),
        migrations.AddConstraint(
            model_name="toxinconcentrationrecord",
            constraint=models.UniqueConstraint(fields=("plant", "pathogen", "nuts_code", "observed_on"), name="uq_toxin_record_scope_day"),
        ),
    ]

