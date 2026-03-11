from django import template

from lumenix.models import SidebarChartLink

register = template.Library()


@register.simple_tag
def dynamic_sidebar_menus():
    """
    Returns active dynamic sidebar menus with active risk-chart submenus.
    Data shape:
    [
      {
        "code": "charts",
        "label": "Charts",
        "icon": "bar-chart-2",
        "items": [SidebarChartLink, ...],
        "identifiers": ["toxin_over_time", ...],
      },
      ...
    ]
    """
    links = (
        SidebarChartLink.active_objects
        .select_related("chart")
        .filter(
            chart__status=1,
            chart__page_code="risk",
        )
        .order_by("menu_code", "order", "id")
    )

    grouped = {}
    ordered_keys = []

    for link in links:
        key = link.menu_code
        icon = (link.menu_icon or "").strip()
        if not icon:
            icon = "bar-chart-2"
        # Backward-compatible override: historical rows used "grid" for Charts.
        # Keep custom explicit icons, but normalize default Charts icon.
        if key == "charts" and icon == "grid":
            icon = "bar-chart-2"

        if key not in grouped:
            grouped[key] = {
                "code": key,
                "label": link.menu_label,
                "icon": icon,
                "items": [],
                "identifiers": [],
            }
            ordered_keys.append(key)
        grouped[key]["items"].append(link)
        grouped[key]["identifiers"].append(link.chart.identifier)

    return [grouped[k] for k in ordered_keys]
