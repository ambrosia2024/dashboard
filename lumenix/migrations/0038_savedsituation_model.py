from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0037_savedsituation_yearly_resolution"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedsituation",
            name="model_uuid",
            field=models.CharField(blank=True, default="", help_text="Chosen source model (ScioModel.external_id / provenance UUID).", max_length=64),
        ),
        migrations.AddField(
            model_name="savedsituation",
            name="model_name",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
    ]
