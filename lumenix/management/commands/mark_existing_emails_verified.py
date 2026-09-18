from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "One-off after enabling mandatory email verification: mark every existing "
        "user's primary address as verified so accounts created before the rule are not locked out. "
        "Use --dry-run to list what would change."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report; change nothing.")

    def handle(self, *args, **options):
        User = get_user_model()
        changed = 0
        for user in User.objects.exclude(email="").order_by("id"):
            address, created = EmailAddress.objects.get_or_create(
                user=user, email__iexact=user.email, defaults={"email": user.email}
            )
            if created or not address.verified or not address.primary:
                self.stdout.write(f"{'would verify' if options['dry_run'] else 'verified'}: {user.email}")
                if not options["dry_run"]:
                    address.verified = True
                    address.primary = True
                    address.save()
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"{changed} address(es) {'to update' if options['dry_run'] else 'updated'}."))
