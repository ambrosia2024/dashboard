from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0032_seed_view_chart_emphasis"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("farmer", "Farmer"),
                    ("forester", "Forester"),
                    ("advisor", "Advisor"),
                    ("food_processor", "Food processor"),
                    ("distributor", "Distributor"),
                    ("policy_maker", "Policy maker"),
                    ("technician", "Technician"),
                    ("other", "Other"),
                ],
                default="",
                help_text="Self-declared role chosen on the preferences page. Empty until the user picks one.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="show_technical_details",
            field=models.BooleanField(
                default=False,
                help_text="Show model inputs and technical terms where available.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="preferences_saved_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the user last saved the preferences page.",
                null=True,
            ),
        ),
    ]
