from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0033_userprofile_role_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="role_other",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Free-text role description, used when role is 'Other'.",
                max_length=100,
            ),
        ),
    ]
