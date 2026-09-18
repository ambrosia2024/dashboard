import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0038_savedsituation_model"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.SmallIntegerField(choices=[(1, "Active"), (0, "Inactive"), (2, "Deleted")], default=1, verbose_name="Status")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("name", models.CharField(max_length=120)),
                ("purpose", models.CharField(choices=[("assess", "Assess my situation"), ("climate_history", "Explore climate history"), ("climate_future", "Explore future climate")], default="assess", max_length=32)),
                ("location_label", models.CharField(blank=True, default="", max_length=255)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("nuts2_code", models.CharField(blank=True, default="", max_length=16)),
                ("nuts2_name", models.CharField(blank=True, default="", max_length=255)),
                ("crop_label", models.CharField(blank=True, default="", max_length=255)),
                ("hazard_label", models.CharField(blank=True, default="", max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("resolution", models.CharField(choices=[("yearly", "Yearly"), ("monthly", "Monthly"), ("weekly", "Weekly"), ("daily", "Daily")], default="monthly", max_length=16)),
                ("model_uuid", models.CharField(blank=True, default="", max_length=64)),
                ("model_name", models.CharField(blank=True, default="", max_length=512)),
                ("run_status", models.CharField(choices=[("completed", "Completed"), ("no_data", "No data"), ("failed", "Failed")], default="completed", max_length=16)),
                ("snapshot", models.JSONField(blank=True, default=dict, help_text="Stored outcome: series, stats, provenance, limitations.")),
                ("crop", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="lumenix.concept")),
                ("hazard", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="lumenix.concept")),
                ("parent_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reruns", to="lumenix.assessmentrun")),
                ("situation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="runs", to="lumenix.savedsituation")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assessment_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "assessment_runs", "ordering": ["-created_at"]},
        ),
    ]
