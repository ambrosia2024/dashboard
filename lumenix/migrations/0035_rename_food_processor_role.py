from django.db import migrations, models


def forwards(apps, schema_editor):
    UserProfile = apps.get_model("lumenix", "UserProfile")
    UserProfile.objects.filter(role="food_processor").update(role="producer")


def backwards(apps, schema_editor):
    UserProfile = apps.get_model("lumenix", "UserProfile")
    UserProfile.objects.filter(role="producer").update(role="food_processor")


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0034_userprofile_role_other"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("farmer", "Farmer"),
                    ("forester", "Forester"),
                    ("advisor", "Advisor"),
                    ("producer", "Producer"),
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
        migrations.RunPython(forwards, backwards),
    ]
