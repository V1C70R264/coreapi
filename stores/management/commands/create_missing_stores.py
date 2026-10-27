# stores/management/commands/create_missing_stores.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from products.models import Product
from stores.services import ensure_store_for


class Command(BaseCommand):
    help = "Create a Store for every user who owns products but has none yet."

    def handle(self, *args, **options):
        User = get_user_model()
        sellers = User.objects.filter(
            id__in=Product.objects.values('seller'),
            store__isnull=True,
        )

        created = 0
        for user in sellers:
            ensure_store_for(user)
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} store(s)."))