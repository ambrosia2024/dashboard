import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0035_rename_food_processor_role"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="adminmenumaster",
            name="badge",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional small label shown next to the menu name, e.g. 'Future'.",
                max_length=20,
                verbose_name="Badge",
            ),
        ),
        migrations.CreateModel(
            name="SavedSituation",
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
                ("nuts2_code", models.CharField(blank=True, default="", help_text="Resolved NUTS2 code, e.g. NL42", max_length=16)),
                ("nuts2_name", models.CharField(blank=True, default="", max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("resolution", models.CharField(choices=[("monthly", "Monthly"), ("weekly", "Weekly"), ("daily", "Daily")], default="monthly", max_length=16)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("crop", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="lumenix.concept")),
                ("hazard", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="lumenix.concept")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_situations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "saved_situations",
                "ordering": ["-last_used_at", "-updated_at"],
            },
        ),
    ]
