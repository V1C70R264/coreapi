from django.core.management import CommandError
from django.core.management.base import BaseCommand

from accounts.email_service import verify_smtp_connection


class Command(BaseCommand):
    help = "Open and close an SMTP connection using Django email settings (no email sent)."

    def handle(self, *args, **options):
        result = verify_smtp_connection()
        if result.ok:
            self.stdout.write(self.style.SUCCESS("SMTP connection OK"))
            return
        self.stderr.write(
            self.style.ERROR(f"SMTP connection failed: {result.error_code} - {result.message}")
        )
        raise CommandError(result.error_code or "smtp_failed")
