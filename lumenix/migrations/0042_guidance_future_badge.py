from django.db import migrations


def forwards(apps, schema_editor):
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    Menu.objects.filter(menu_route="guidance", menu_type=1).update(badge="Future")


def backwards(apps, schema_editor):
    Menu = apps.get_model("lumenix", "AdminMenuMaster")
    Menu.objects.filter(menu_route="guidance", menu_type=1).update(badge="")


class Migration(migrations.Migration):

    dependencies = [("lumenix", "0041_seed_v2_sidebar_menu")]

    operations = [migrations.RunPython(forwards, backwards)]
