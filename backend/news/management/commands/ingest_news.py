"""Fetch live articles from configured providers and store them."""
from django.core.management.base import BaseCommand

from news.services import aggregator


class Command(BaseCommand):
    help = (
        "Fetch news from configured RSS/API providers. Use --all for every feed, "
        "--query to run a topic search, otherwise the balanced home feed is fetched."
    )

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Fetch every configured feed.")
        parser.add_argument(
            "--query", type=str, default="", help="Search a topic and store the results."
        )

    def handle(self, *args, **options):
        if options["query"]:
            stats = aggregator.search_news(options["query"])
            self._report(stats, f"search '{options['query']}'")
            return

        if options["all"]:
            stats = aggregator.ingest_all_feeds()
            self._report(stats, "all feeds")
            return

        stats = aggregator.refresh_feed(force=True, scope="general")
        self._report(stats, "balanced feed")

    def _report(self, stats: dict, label: str) -> None:
        if stats.get("skipped"):
            self.stdout.write(self.style.WARNING(f"Skipped ({stats.get('reason')})."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}: received {stats.get('received', 0)}, "
                f"created {stats['created']}, updated {stats['updated']}, "
                f"duplicates skipped {stats['duplicates_skipped']}"
            )
        )
        self.stdout.write(
            f"  providers: {stats.get('providers_succeeded', 0)}"
            f"/{stats.get('providers_attempted', 0)} succeeded"
        )
        for error in stats.get("errors", []):
            self.stdout.write(self.style.WARNING(f"  ! {error}"))
