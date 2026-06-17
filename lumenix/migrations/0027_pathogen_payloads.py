from django.db import migrations, models


def backfill_pathogen_payloads(apps, schema_editor):
    PathogenConcentrationRecord = apps.get_model("lumenix", "PathogenConcentrationRecord")

    batch = []
    for record in PathogenConcentrationRecord.objects.all().iterator(chunk_size=1000):
        request_payload = {
            "plant": record.plant,
            "pathogen": record.pathogen,
            "nutsCode": record.nuts_code,
            "startDate": record.observed_on.isoformat(),
            "endDate": record.observed_on.isoformat(),
            "timeScale": "daily",
        }
        provenance_payload = {
            "model_id": record.provenance_model_id,
            "model_title": record.provenance_model_title,
            "variable_name": record.provenance_variable_name,
            "fetched_at": record.provenance_fetched_at_ms,
        }
        record.request_payload = request_payload
        record.provenance_payload = provenance_payload
        batch.append(record)
        if len(batch) >= 1000:
            PathogenConcentrationRecord.objects.bulk_update(
                batch,
                ["request_payload", "provenance_payload"],
                batch_size=1000,
            )
            batch = []

    if batch:
        PathogenConcentrationRecord.objects.bulk_update(
            batch,
            ["request_payload", "provenance_payload"],
            batch_size=1000,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0026_alter_sciomodel_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pathogenconcentrationrecord",
            name="request_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pathogenconcentrationrecord",
            name="provenance_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_pathogen_payloads, migrations.RunPython.noop),
    ]
