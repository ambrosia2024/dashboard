from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0036_savedsituation_menu_badge"),
    ]

    operations = [
        migrations.AlterField(
            model_name="savedsituation",
            name="resolution",
            field=models.CharField(
                choices=[("yearly", "Yearly"), ("monthly", "Monthly"), ("weekly", "Weekly"), ("daily", "Daily")],
                default="monthly",
                max_length=16,
            ),
        ),
    ]
