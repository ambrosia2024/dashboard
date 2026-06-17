# Generated manually to rename the pathogen sync pipeline away from legacy toxin names.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0024_alter_adminmenumaster_menu_route"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ToxinQuerySpec",
            new_name="PathogenQuerySpec",
        ),
        migrations.RenameModel(
            old_name="ToxinConcentrationRecord",
            new_name="PathogenConcentrationRecord",
        ),
        migrations.RenameField(
            model_name="pathogenconcentrationrecord",
            old_name="toxin_value",
            new_name="pathogen_model_value",
        ),
        migrations.RemoveConstraint(
            model_name="pathogenqueryspec",
            name="uq_toxin_query_spec_scope",
        ),
        migrations.RemoveConstraint(
            model_name="pathogenconcentrationrecord",
            name="uq_toxin_record_scope_day",
        ),
        migrations.AlterModelTable(
            name="pathogenqueryspec",
            table="pathogen_query_specs",
        ),
        migrations.AlterModelTable(
            name="pathogenconcentrationrecord",
            table="pathogen_concentration_records",
        ),
        migrations.AlterModelOptions(
            name="pathogenqueryspec",
            options={
                "ordering": ["name"],
                "verbose_name": "Pathogen query spec",
                "verbose_name_plural": "Pathogen query specs",
            },
        ),
        migrations.AlterModelOptions(
            name="pathogenconcentrationrecord",
            options={
                "ordering": ["observed_on"],
                "verbose_name": "Pathogen concentration record",
                "verbose_name_plural": "Pathogen concentration records",
            },
        ),
        migrations.AddConstraint(
            model_name="pathogenqueryspec",
            constraint=models.UniqueConstraint(
                fields=("plant", "pathogen", "nuts_code", "start_date", "end_date", "time_scale"),
                name="uq_pathogen_query_spec_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="pathogenconcentrationrecord",
            constraint=models.UniqueConstraint(
                fields=("plant", "pathogen", "nuts_code", "observed_on"),
                name="uq_pathogen_record_scope_day",
            ),
        ),
    ]
