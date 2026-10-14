from django.db import migrations

# The Europe growth map is a demo (model-derived from the synced temperatures,
# not validated), so the menu says so, and it sits right after External
# Resources. Menu orders differ per environment (they are edited in admin), so
# the item is placed relative to External Resources and the top-level items are
# renumbered 10, 20, 30... in their current display order, leaving gaps for
# later edits in admin.
PARENT, ITEM = 0, 1  # AdminMenuMaster.MenuType
ROUTE = "pathogen-growth"


def place_and_mark_demo(apps, schema_editor):
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    item = Menu.objects.filter(menu_route=ROUTE, menu_type=ITEM).first()
    if item is None:
        return
    item.note = "demo"
    item.save(update_fields=["note"])

    tops = list(Menu.objects.filter(menu_type__in=[PARENT, ITEM]).order_by("order", "id"))
    anchor = next((m for m in tops if m.menu_type == PARENT and m.menu_name == "External Resources"), None)
    if anchor is None:
        return
    tops = [m for m in tops if m.pk != item.pk]
    tops.insert(tops.index(anchor) + 1, item)
    for position, row in enumerate(tops, start=1):
        if row.order != position * 10:
            row.order = position * 10
            row.save(update_fields=["order"])


def clear_demo_note(apps, schema_editor):
    # The new order is kept: it is the same display order with gaps.
    apps.get_model("lumenix", "AdminMenuMaster").objects.filter(
        menu_route=ROUTE, menu_type=ITEM
    ).update(note="")


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0047_cardinal_growth"),
    ]

    operations = [
        migrations.RunPython(place_and_mark_demo, clear_demo_note),
    ]
