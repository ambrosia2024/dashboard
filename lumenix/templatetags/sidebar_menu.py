import re

from django import template
from django.urls import reverse, NoReverseMatch

from lumenix.models import SidebarChartLink, AdminMenuMaster
from lumenix.services.dashboard_modes import get_active_mode, chart_emphasis_map

register = template.Library()

# Matches a leading chart-code prefix like "C1 - " / "c2 – " used in chart labels.
_CHART_CODE_PREFIX = re.compile(r"^[Cc]\d+\s*[-–—:]\s*")

# Pulls the chart identifier out of a /risk-charts/chart/<id>/ menu route.
_CHART_LINK_RE = re.compile(r"/risk-charts/chart/([^/]+)/")


@register.filter
def strip_chart_code(label):
    """Drop the leading "C1 - " style code so labels match the sidebar names."""
    return _CHART_CODE_PREFIX.sub("", (label or "").strip())


def _resolve_menu_url(route):
    """Resolve a menu_route to an href.

    Accepts a Django URL name (e.g. 'dashboard'), an absolute path
    ('/risk-charts/...'), or a full external URL ('https://...').
    """
    route = (route or "").strip()
    if not route:
        return ""
    if route.startswith(("http://", "https://", "//", "/")):
        return route
    try:
        return reverse(route)
    except NoReverseMatch:
        return route


def _is_active(url, current_path):
    if not url or url.startswith(("http://", "https://", "//")):
        return False
    return url.rstrip("/") == (current_path or "").rstrip("/")


@register.simple_tag(takes_context=True)
def admin_menu_tree(context):
    """Build the sidebar tree from AdminMenuMaster (active rows only).

    Returns a list of top-level nodes (Parent groups and clickable Items),
    each Parent carrying its active Submenu children, with resolved urls and
    an `active` flag derived from the current request path.
    """
    request = context.get("request")
    current_path = getattr(request, "path", "") if request else ""

    # Per-view chart emphasis, so chart links can be greyed-out for the active view.
    emphasis_map = chart_emphasis_map(get_active_mode(request)) if request else {}

    nodes = list(AdminMenuMaster.active_objects.order_by("order", "id"))
    children_by_parent = {}
    tops = []
    for node in nodes:
        if node.menu_type == AdminMenuMaster.MenuType.SUBMENU and node.parent_id:
            children_by_parent.setdefault(node.parent_id, []).append(node)
        elif node.menu_type in (AdminMenuMaster.MenuType.PARENT, AdminMenuMaster.MenuType.ITEM):
            tops.append(node)

    tree = []
    for node in tops:
        is_parent = node.menu_type == AdminMenuMaster.MenuType.PARENT
        url = _resolve_menu_url(node.menu_route)
        children = []
        any_child_active = False
        if is_parent:
            for child in children_by_parent.get(node.id, []):
                child_url = _resolve_menu_url(child.menu_route)
                child_active = _is_active(child_url, current_path)
                any_child_active = any_child_active or child_active
                chart_match = _CHART_LINK_RE.search(child_url or "")
                emphasis = emphasis_map.get(chart_match.group(1)) if chart_match else None
                children.append({
                    "name": child.menu_name,
                    "url": child_url,
                    "open_in_new_tab": child.open_in_new_tab,
                    "active": child_active,
                    "emphasis": emphasis,
                })
        tree.append({
            "name": node.menu_name,
            "icon": node.menu_icon or "circle",
            "url": url,
            "is_parent": is_parent,
            "open_in_new_tab": node.open_in_new_tab,
            "active": any_child_active or _is_active(url, current_path),
            "children": children,
        })
    return tree


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
