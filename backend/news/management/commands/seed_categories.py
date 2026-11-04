"""Create the standard NewsHub categories (idempotent)."""
from django.core.management.base import BaseCommand

from news.services.aggregator import ensure_categories
from news.models import Category


class Command(BaseCommand):
    help = "Create the default NewsHub categories if they do not exist."

    def handle(self, *args, **options):
        ensure_categories()
        self.stdout.write(
            self.style.SUCCESS(f"Categories available: {Category.objects.count()}")
        )
        for category in Category.objects.all():
            self.stdout.write(f"  - {category.slug:<24} {category.name}")
