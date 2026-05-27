from django.core.management import CommandError
from django.core.management.base import BaseCommand

from accounts.email_service import send_plain_email


class Command(BaseCommand):
    help = "Send a real test email through the configured SMTP backend."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            default="victorshirima295@gmail.com",
            help="Recipient email address (default: victorshirima295@gmail.com)",
        )
        parser.add_argument(
            "--subject",
            default="CoreAPI SMTP test",
            help="Email subject",
        )

    def handle(self, *args, **options):
        to = options["to"]
        subject = options["subject"]
        body = (
            "This is a test message from CoreAPI.\n\n"
            "If you received this, Django SMTP settings are working.\n"
        )
        result = send_plain_email(subject, body, [to], fail_silently=False)
        if result.ok:
            self.stdout.write(self.style.SUCCESS(f"Sent test email to {to}"))
            return
        self.stderr.write(self.style.ERROR(f"Failed: {result.error_code} - {result.message}"))
        raise CommandError(result.error_code or "send_failed")
