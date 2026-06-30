from django.db import migrations

# Per-view chart emphasis from docs/ambrosia_views_chart_spec.docx.pdf, Section 2
# (View -> Chart Mapping matrix). P = Primary, S = Secondary, X = Disabled (the
# spec's "Not Included"; we keep it visible-but-greyed per product decision).
#
#                       default advisor policy   producer distrib technician
EMPHASIS_MATRIX = {
    "c1_toxin_over_time":         ["P", "P", "S", "P", "P", "P"],
    "c2_pathogen_over_time":      ["S", "P", "S", "P", "S", "P"],
    "c3_probability_over_time":   ["S", "P", "P", "S", "S", "P"],
    "c4_cases_per_100k":          ["S", "S", "P", "X", "X", "S"],
    "c5_seasonal_heatmap":        ["P", "P", "P", "P", "P", "P"],
    "c6_geographic_risk_heatmap": ["P", "P", "P", "P", "P", "P"],
    "c7_climate_scenarios":       ["S", "P", "P", "S", "X", "P"],
}

MODE_CODES = ["default", "advisor", "policy-actor", "producer", "distributor", "technician"]

LETTER_TO_EMPHASIS = {"P": "primary", "S": "secondary", "X": "disabled"}

# Order charts within a view by their C-number (c1..c7 -> 1..7).
CHART_ORDER = {ident: i + 1 for i, ident in enumerate(EMPHASIS_MATRIX.keys())}


def seed_emphasis(apps, schema_editor):
    DashboardViewMode = apps.get_model("lumenix", "DashboardViewMode")
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    DashboardViewChart = apps.get_model("lumenix", "DashboardViewChart")

    modes = {m.code: m for m in DashboardViewMode.objects.filter(code__in=MODE_CODES)}
    charts = {c.identifier: c for c in DashboardChart.objects.filter(identifier__in=EMPHASIS_MATRIX.keys())}

    for identifier, letters in EMPHASIS_MATRIX.items():
        chart = charts.get(identifier)
        if not chart:
            continue
        for code, letter in zip(MODE_CODES, letters):
            mode = modes.get(code)
            if not mode:
                continue
            DashboardViewChart.objects.update_or_create(
                mode=mode,
                chart=chart,
                defaults={
                    "emphasis": LETTER_TO_EMPHASIS[letter],
                    "order": CHART_ORDER[identifier],
                    "status": 1,
                },
            )


def noop_reverse(apps, schema_editor):
    # Leave seeded rows in place on reverse; the schema migration handles the column.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0031_dashboardviewchart_emphasis"),
    ]

    operations = [
        migrations.RunPython(seed_emphasis, noop_reverse),
    ]
