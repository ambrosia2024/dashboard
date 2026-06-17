from django.db import migrations


# Promote four All-Charts visualisations to standalone risk charts, mirroring the
# existing c1/c2/c3 DashboardChart records. Data-driven so it ships with the image.
STANDALONE_CHARTS = [
    {
        "identifier": "c4_cases_per_100k",
        "label": "C4 - Cases per 100k vs time",
        "template_name": "lumenix/charts/risk/cases_per_100k.html",
        "title": "Cases per 100k vs time",
    },
    {
        "identifier": "c5_seasonal_heatmap",
        "label": "C5 - Seasonal heatmap (× baseline)",
        "template_name": "lumenix/charts/risk/seasonal_heatmap.html",
        "title": "Seasonal heatmap (× baseline)",
    },
    {
        "identifier": "c6_geographic_risk_heatmap",
        "label": "C6 - Geographic Risk Heatmap",
        "template_name": "lumenix/charts/risk/geographic_risk_heatmap.html",
        "title": "Geographic Risk Heatmap",
    },
    {
        "identifier": "c7_climate_scenarios",
        "label": "C7 - Climate-adjusted scenarios vs time",
        "template_name": "lumenix/charts/risk/climate_scenarios.html",
        "title": "Climate-adjusted scenarios vs time",
    },
]


def create_charts(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    for chart in STANDALONE_CHARTS:
        DashboardChart.objects.update_or_create(
            identifier=chart["identifier"],
            defaults={
                "label": chart["label"],
                "template_name": chart["template_name"],
                "page_code": "risk",
                "default_config": {"title": chart["title"]},
                "status": 1,
            },
        )


def remove_charts(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    DashboardChart.objects.filter(
        identifier__in=[c["identifier"] for c in STANDALONE_CHARTS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0027_pathogen_payloads"),
    ]

    operations = [
        migrations.RunPython(create_charts, remove_charts),
    ]
