from django.db import migrations

# V2 sidebar (design 02): the rows that were created by hand on the local
# database, so every environment gets the same menu on migrate. Idempotent:
# rows are matched by route and only created or updated, never duplicated.
ITEM = 1  # AdminMenuMaster.MenuType.ITEM

V2_ITEMS = [
    # name,               route,                        icon,          order, badge
    ("Overview",          "overview",                   "user",        0,     ""),
    ("New assessment",    "assessment-new",             "plus-circle", 1,     ""),
    ("Saved situations",  "situations",                 "bookmark",    2,     ""),
    ("History",           "/situations/?tab=history",   "clock",       3,     ""),
    ("Guidance",          "guidance",                   "book-open",   4,     ""),
    ("Supply chain",      "supply-chain",               "git-branch",  5,     "Future"),
]


def forwards(apps, schema_editor):
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    for name, route, icon, order, badge in V2_ITEMS:
        row, created = Menu.objects.get_or_create(
            menu_route=route, menu_type=ITEM,
            defaults={"menu_name": name, "menu_icon": icon, "order": order, "status": 1, "badge": badge},
        )
        if not created:
            row.menu_name, row.menu_icon, row.order, row.status, row.badge = name, icon, order, 1, badge
            row.save()
    # The old landing page is reachable at /dashboard/ but no longer listed.
    Menu.objects.filter(menu_route="dashboard", menu_type=ITEM).update(status=0)


def backwards(apps, schema_editor):
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    Menu.objects.filter(menu_route__in=[r for _, r, *_ in V2_ITEMS], menu_type=ITEM).update(status=0)
    Menu.objects.filter(menu_route="dashboard", menu_type=ITEM).update(status=1)


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0040_ambramessage"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
