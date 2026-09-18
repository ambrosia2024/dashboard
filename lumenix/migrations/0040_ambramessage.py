import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0039_assessmentrun"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AmbraMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "User"), ("ambra", "Ambra")], max_length=8)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ambra_messages", to="lumenix.assessmentrun")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ambra_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "ambra_messages", "ordering": ["created_at", "id"]},
        ),
    ]
