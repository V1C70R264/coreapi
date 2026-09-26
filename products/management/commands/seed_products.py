from pathlib import Path
from django.core.files import File
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from products.models import Product, Category

User = get_user_model()

SEED_IMAGES_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'seed_images'

CATEGORIES = [
    "Phones & Tablets",
    "Electronics",
    "Fashion",
    "Home & Kitchen",
    "Groceries",
    "Beauty & Personal Care",
]

PRODUCTS = [
    # Phones & Tablets
    {
        "name": "iPhone 15",
        "description": "Latest Apple smartphone with A16 chip",
        "price": "1200000.00",
        "stock_quantity": 10,
        "category": "Phones & Tablets",
        "image_file": "iphone15.jpg",
    },
    {
        "name": "Samsung Galaxy Tab A9",
        "description": "Affordable Android tablet for everyday use",
        "price": "450000.00",
        "stock_quantity": 12,
        "category": "Phones & Tablets",
        "image_file": "galaxy_tab_a9.jpg",
    },

    # Electronics
    {
        "name": "JBL Bluetooth Speaker",
        "description": "Portable wireless speaker with deep bass",
        "price": "85000.00",
        "stock_quantity": 20,
        "category": "Electronics",
        "image_file": "jbl_speaker.jpg",
    },
    {
        "name": "Sony Wireless Headphones",
        "description": "Noise-cancelling over-ear headphones",
        "price": "150000.00",
        "stock_quantity": 15,
        "category": "Electronics",
        "image_file": "sony_headphones.jpg",
    },

    # Fashion
    {
        "name": "Men's Cotton T-Shirt",
        "description": "Comfortable everyday casual wear",
        "price": "25000.00",
        "stock_quantity": 50,
        "category": "Fashion",
        "image_file": "tshirt.jpg",
    },
    {
        "name": "Women's Ankara Dress",
        "description": "Vibrant African print dress",
        "price": "60000.00",
        "stock_quantity": 25,
        "category": "Fashion",
        "image_file": "ankara_dress.jpg",
    },

    {
        "name": "Modern Ankara Dress",
        "description": "Exciting African Traditional dress",
        "price": "70000.00",
        "stock_quantity": 25,
        "category": "Fashion",
        "image_file": "ankara_dress2.jpg",
    },



    # Home & Kitchen
    {
        "name": "Non-stick Frying Pan",
        "description": "Durable kitchen frying pan",
        "price": "35000.00",
        "stock_quantity": 20,
        "category": "Home & Kitchen",
        "image_file": "frying_pan.jpg",
    },
    {
        "name": "Electric Kettle 1.7L",
        "description": "Fast-boil stainless steel kettle",
        "price": "45000.00",
        "stock_quantity": 18,
        "category": "Home & Kitchen",
        "image_file": "electric_kettle.jpg",
    },

    # Groceries
    {
        "name": "Rice 5kg Bag",
        "description": "Premium quality rice",
        "price": "18000.00",
        "stock_quantity": 100,
        "category": "Groceries",
        "image_file": "rice_5kg.jpg",
    },
    {
        "name": "Cooking Oil 2L",
        "description": "Pure vegetable cooking oil",
        "price": "12000.00",
        "stock_quantity": 80,
        "category": "Groceries",
        "image_file": "cooking_oil.jpg",
    },

    # Beauty & Personal Care
    {
        "name": "Shea Butter Body Lotion",
        "description": "Moisturizing lotion for all skin types",
        "price": "15000.00",
        "stock_quantity": 40,
        "category": "Beauty & Personal Care",
        "image_file": "shea_lotion.jpg",
    },
    {
        "name": "Men's Grooming Kit",
        "description": "Trimmer and shaving set",
        "price": "55000.00",
        "stock_quantity": 15,
        "category": "Beauty & Personal Care",
        "image_file": "grooming_kit.jpg",
    },
]


class Command(BaseCommand):
    help = "Seeds the database with sample categories and products, using local image files."

    def add_arguments(self, parser):
        parser.add_argument('--seller-username', type=str, default=None)

    def handle(self, *args, **options):
        seller = self._get_seller(options['seller_username'])
        self.stdout.write(f"Seeding as seller: {seller.username}")
        self.stdout.write(f"Looking for images in: {SEED_IMAGES_DIR}")

        if not SEED_IMAGES_DIR.exists():
            self.stderr.write(self.style.ERROR(
                f"Image directory not found: {SEED_IMAGES_DIR}. "
                "Create it and add your product images first."
            ))
            return

        category_map = {}
        for name in CATEGORIES:
            category, created = Category.objects.get_or_create(
                name=name, defaults={'description': f"{name} category"},
            )
            category_map[name] = category
            self.stdout.write(f"  Category: {name} {'(created)' if created else '(exists)'}")

        created_count = 0
        skipped_count = 0

        for product_data in PRODUCTS:
            if Product.objects.filter(name=product_data['name']).exists():
                self.stdout.write(f"  Skipping (already exists): {product_data['name']}")
                skipped_count += 1
                continue

            image_path = SEED_IMAGES_DIR / product_data['image_file']
            if not image_path.exists():
                self.stdout.write(self.style.WARNING(
                    f"  Skipping {product_data['name']} — image not found: {image_path}"
                ))
                skipped_count += 1
                continue

            product = Product(
                name=product_data['name'],
                description=product_data['description'],
                price=product_data['price'],
                stock_quantity=product_data['stock_quantity'],
                category=category_map[product_data['category']],
                seller=seller,
            )
            with open(image_path, 'rb') as f:
                product.image.save(product_data['image_file'], File(f), save=True)

            self.stdout.write(self.style.SUCCESS(f"  Created: {product_data['name']}"))
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created: {created_count}, Skipped: {skipped_count}"
        ))

    def _get_seller(self, username):
        if username:
            return User.objects.get(username=username)
        seller = User.objects.filter(is_staff=True).first()
        if not seller:
            raise ValueError("No staff user found. Create one with 'createsuperuser'.")
        return seller