# lumenix/management/commands/verify_superuser_emails.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress


class Command(BaseCommand):
    help = "Mark all superuser email addresses as verified for django-allauth."

    def handle(self, *args, **options):
        User = get_user_model()
        count = 0

        for user in User.objects.filter(is_superuser=True):
            if not user.email:
                continue

            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": True},
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Verified email for {count} superuser(s)."))
