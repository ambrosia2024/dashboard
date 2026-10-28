from django.db import migrations

# The two growth-potential charts also exist on the assessment outcome page,
# where they are computed from the synced model output. Reviewers reached the
# outcome page without ever meeting them under Charts, so the same two charts
# are added here as illustrative twins, fed by the shared dummy generator.
PARENT, SUBMENU = 0, 2  # AdminMenuMaster.MenuType

CHARTS = [
    {
        "identifier": "c8_growth_potential_change",
        "label": "C8 - Projected change in modelled growth potential",
        "template_name": "lumenix/charts/risk/growth_potential_change.html",
        "title": "Projected change in modelled growth potential",
        "menu_name": "Projected change in growth potential",
        "order": 8,
    },
    {
        "identifier": "c9_growth_potential_over_time",
        "label": "C9 - Modelled growth potential over time",
        "template_name": "lumenix/charts/risk/growth_potential_over_time.html",
        "title": "Modelled growth potential over time",
        "menu_name": "Growth potential over time",
        "order": 9,
    },
]

MODE_CODES = ["default", "advisor", "policy-actor", "producer", "distributor", "technician"]


def add_charts(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    DashboardViewMode = apps.get_model("lumenix", "DashboardViewMode")
    DashboardViewChart = apps.get_model("lumenix", "DashboardViewChart")
    Menu = apps.get_model("lumenix", "AdminMenuMaster")

    modes = list(DashboardViewMode.objects.filter(code__in=MODE_CODES))
    # The menu is edited per environment, so the parent is found by name rather
    # than by a hardcoded id, and the children are appended after the last one.
    parent = Menu.objects.filter(menu_type=PARENT, menu_name__iexact="Charts").first()
    next_order = 0
    if parent is not None:
        last = (
            Menu.objects.filter(menu_type=SUBMENU, parent=parent)
            .order_by("-order")
            .first()
        )
        next_order = (last.order if last else 0) + 10

    for entry in CHARTS:
        chart, _ = DashboardChart.objects.update_or_create(
            identifier=entry["identifier"],
            defaults={
                "label": entry["label"],
                "template_name": entry["template_name"],
                "page_code": "risk",
                "default_config": {"title": entry["title"], "data_source": "dummy"},
                "status": 1,
            },
        )

        # Available in every view: these two are the demo counterpart of what the
        # outcome page shows everyone, so greying them out per role would mislead.
        for mode in modes:
            DashboardViewChart.objects.update_or_create(
                mode=mode,
                chart=chart,
                defaults={"emphasis": "primary", "order": entry["order"], "status": 1},
            )

        if parent is None:
            continue
        route = "/risk-charts/chart/%s/" % entry["identifier"]
        _, created = Menu.objects.update_or_create(
            menu_route=route,
            menu_type=SUBMENU,
            defaults={
                "menu_name": entry["menu_name"],
                "parent": parent,
                "order": next_order,
                "status": 1,
            },
        )
        if created:
            next_order += 10


def remove_charts(apps, schema_editor):
    DashboardChart = apps.get_model("lumenix", "DashboardChart")
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    identifiers = [c["identifier"] for c in CHARTS]

    Menu.objects.filter(
        menu_type=SUBMENU,
        menu_route__in=["/risk-charts/chart/%s/" % i for i in identifiers],
    ).delete()
    # DashboardViewChart rows cascade with the chart.
    DashboardChart.objects.filter(identifier__in=identifiers).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0049_userprofile_cohort_userevent"),
    ]

    operations = [
        migrations.RunPython(add_charts, remove_charts),
    ]
