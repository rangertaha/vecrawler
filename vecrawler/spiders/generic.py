import re
from urllib.parse import urlparse

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule as ScrapyRule

from vecrawler.pipelines import _setup_django


class GenericSpider(CrawlSpider):
    """A CrawlSpider whose behavior is driven by a Django `Crawler` row.

    Domains, paths, link rules, and throttling all come from the database, so a
    crawl is configured entirely in the Django admin:

        scrapy crawl generic -a config=<slug-or-name>

    Optionally override the seed without touching the DB:

        scrapy crawl generic -a config=my-site -a start_url=https://example.com/x
    """

    name = "generic"

    # Export scraped items to a timestamped CSV (alongside the Entity save).
    custom_settings = {
        "FEEDS": {
            "output/%(name)s-%(time)s.csv": {"format": "csv"},
        },
    }

    def __init__(self, config=None, start_url=None, *args, **kwargs):
        if not config:
            raise ValueError(
                "generic spider requires a Django crawler config, e.g. "
                "scrapy crawl generic -a config=<slug-or-name>"
            )

        _setup_django()
        from django.db.models import Q
        from crawler.models import Crawler

        try:
            cfg = Crawler.objects.get(Q(slug=config) | Q(name=config))
        except Crawler.DoesNotExist:
            raise ValueError(f"No Django Crawler matches slug/name {config!r}")

        self.config = cfg
        self.config_name = cfg.name

        # --- Domains -> allowed_domains + start_urls -------------------------
        domains = list(cfg.domains.filter(enabled=True))
        self.allowed_domains = [d.host for d in domains if d.host]

        if start_url:
            self.start_urls = [start_url]
            # Make sure a manual start_url's host is allowed.
            host = urlparse(start_url).netloc
            if host and host not in self.allowed_domains:
                self.allowed_domains.append(host)
        else:
            self.start_urls = self._build_start_urls(cfg, domains)

        if not self.start_urls:
            raise ValueError(
                f"Crawler {cfg.name!r} has no enabled domains / start URLs"
            )

        # --- Per-spider throttling knobs (honored by the downloader) --------
        self.download_delay = cfg.download_delay
        self.max_concurrent_requests = cfg.concurrent_requests

        # --- Field extraction: snapshot template Items' Props (no ORM in
        #     callbacks). Only Items flagged is_template act as templates.
        self._props = [
            {"name": p.name, "css": p.css, "xpath": p.xpath,
             "regex": p.regex, "many": p.many}
            for item in cfg.items.filter(is_template=True).prefetch_related("props")
            for p in item.props.all()
        ]

        # --- Rules -> CrawlSpider rules (set before super()._compile_rules) -
        self.rules = self._build_rules(cfg)

        super().__init__(*args, **kwargs)

    @staticmethod
    def _build_start_urls(cfg, domains):
        """Seed URLs from the crawler's domains."""
        urls = [d.start_url or f"https://{d.host}" for d in domains]
        # De-duplicate while preserving order.
        seen, ordered = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered

    def _valid_regex(self, pattern, field, rule):
        """Return the pattern if it compiles, else warn and drop it."""
        try:
            re.compile(pattern)
            return pattern
        except re.error as exc:
            self.logger.warning(
                "Rule %r: invalid %s regex %r (%s) — ignored",
                rule.name or rule.pk, field, pattern, exc,
            )
            return None

    def _build_rules(self, cfg):
        rules = []
        for r in cfg.rules.all():
            le_kwargs = {}
            allow = self._valid_regex(r.allow, "allow", r) if r.allow else None
            if allow:
                le_kwargs["allow"] = allow
            deny = self._valid_regex(r.deny, "deny", r) if r.deny else None
            if deny:
                le_kwargs["deny"] = deny
            if r.allow_domains:
                le_kwargs["allow_domains"] = self._split(r.allow_domains)
            if r.deny_domains:
                le_kwargs["deny_domains"] = self._split(r.deny_domains)
            if r.restrict_css:
                le_kwargs["restrict_css"] = r.restrict_css
            if r.restrict_xpaths:
                le_kwargs["restrict_xpaths"] = r.restrict_xpaths

            rules.append(
                ScrapyRule(
                    LinkExtractor(**le_kwargs),
                    callback=r.callback or "parse_item",
                    follow=r.follow,
                )
            )

        # No rules configured -> follow everything and parse every page.
        if not rules:
            rules.append(
                ScrapyRule(LinkExtractor(), callback="parse_item", follow=True)
            )
        return tuple(rules)

    @staticmethod
    def _split(value):
        return [v.strip() for v in value.split(",") if v.strip()]

    def parse_item(self, response):
        # `url`/`title` are always captured; `content` feeds the Ollama parser.
        item = {
            "url": response.url,
            "title": (response.css("title::text").get() or "").strip(),
            "content": self._page_text(response),
        }
        # Apply each configured Prop (css / xpath / regex) to extract a field.
        for p in self._props:
            value = self._extract(response, p)
            if value not in (None, [], ""):
                item[p["name"]] = value
        yield item

    @staticmethod
    def _page_text(response):
        """Visible text of the page (truncated), for the LLM parser."""
        if not response.headers.get("Content-Type", b"").startswith(b"text/html"):
            return ""
        parts = response.xpath(
            "//body//text()[not(ancestor::script) and not(ancestor::style)]"
        ).getall()
        text = " ".join(t.strip() for t in parts if t.strip())
        return text[:8000]

    @staticmethod
    def _extract(response, p):
        many = p["many"]
        if p["xpath"]:
            sel = response.xpath(p["xpath"])
            return sel.getall() if many else sel.get()
        if p["css"]:
            sel = response.css(p["css"])
            return sel.getall() if many else sel.get()
        if p["regex"]:
            matches = re.findall(p["regex"], response.text)
            return matches if many else (matches[0] if matches else None)
        return None
