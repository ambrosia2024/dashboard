from django.db import migrations


# Marks which risk charts are backed by real synced data vs. illustrative/generated
# values, so each chart page can show a Live/Demo badge. Only the pathogen chart is
# wired to a real source (SCiO); the rest use the shared dummy generator.
REAL_CHARTS = {"c2_pathogen_over_time"}
ALL_CHARTS = [
    "c1_toxin_over_time",
    "c2_pathogen_over_time",
    "c3_probability_over_time",
    "c4_cases_per_100k",
    "c5_seasonal_heatmap",
    "c6_geographic_risk_heatmap",
    "c7_climate_scenarios",
]


def set_data_source(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    for identifier in ALL_CHARTS:
        chart = DashboardChart.objects.filter(identifier=identifier).first()
        if not chart:
            continue
        cfg = dict(chart.default_config or {})
        cfg["data_source"] = "real" if identifier in REAL_CHARTS else "dummy"
        chart.default_config = cfg
        chart.save(update_fields=["default_config"])


def unset_data_source(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    for identifier in ALL_CHARTS:
        chart = DashboardChart.objects.filter(identifier=identifier).first()
        if not chart:
            continue
        cfg = dict(chart.default_config or {})
        cfg.pop("data_source", None)
        chart.default_config = cfg
        chart.save(update_fields=["default_config"])


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0028_add_standalone_risk_charts"),
    ]

    operations = [
        migrations.RunPython(set_data_source, unset_data_source),
    ]
