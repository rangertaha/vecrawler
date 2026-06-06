"""Run a Scrapy crawl driven by a Django Crawler config.

    python manage.py runcrawler <slug-or-name>
    python manage.py runcrawler my-site --start-url https://example.com/section
    python manage.py runcrawler my-site -s CLOSESPIDER_ITEMCOUNT=20
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from crawler.models import Crawler


class Command(BaseCommand):
    help = "Run the generic Scrapy spider for a Django Crawler config."

    def add_arguments(self, parser):
        parser.add_argument(
            "config", help="Slug or name of the Crawler to run"
        )
        parser.add_argument(
            "--start-url",
            dest="start_url",
            default=None,
            help="Override the seed URL without editing the config",
        )
        parser.add_argument(
            "-s",
            "--set",
            dest="overrides",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="Override a Scrapy setting (repeatable)",
        )

    def handle(self, *args, **options):
        config = options["config"]

        try:
            crawler = Crawler.objects.get(Q(slug=config) | Q(name=config))
        except Crawler.DoesNotExist:
            available = ", ".join(Crawler.objects.values_list("slug", flat=True)) or "(none)"
            raise CommandError(
                f"No Crawler matches {config!r}. Available: {available}"
            )

        if not crawler.enabled:
            raise CommandError(f"Crawler {crawler.slug!r} is disabled.")

        # Import Scrapy lazily so non-crawl management commands stay light.
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings

        settings = get_project_settings()

        # Apply the crawler's HTTP cache settings (overridable by -s below).
        settings.set("HTTPCACHE_ENABLED", crawler.cache_enabled, priority="cmdline")
        settings.set(
            "HTTPCACHE_EXPIRATION_SECS", crawler.cache_expiration_secs, priority="cmdline"
        )
        settings.set("HTTPCACHE_DIR", crawler.cache_dir, priority="cmdline")

        for override in options["overrides"]:
            key, _, value = override.partition("=")
            settings.set(key.strip(), value.strip(), priority="cmdline")

        spider_kwargs = {"config": crawler.slug}
        if options["start_url"]:
            spider_kwargs["start_url"] = options["start_url"]

        cache_state = "on" if crawler.cache_enabled else "off"
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Crawling {crawler.name!r} "
                f"(delay={crawler.download_delay}s, "
                f"concurrency={crawler.concurrent_requests}, "
                f"cache={cache_state})…"
            )
        )

        process = CrawlerProcess(settings)
        process.crawl("generic", **spider_kwargs)
        process.start()  # blocks until the crawl finishes

        count = crawler.items.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {crawler.name!r} now has {count} stored item(s)."
            )
        )
