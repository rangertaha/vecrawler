from django.db import models
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey


class Crawler(models.Model):
    """A configurable crawler — the Django-side definition of a Scrapy spider."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    # Scrapy run-time knobs (override project defaults when set).
    concurrent_requests = models.PositiveIntegerField(
        default=16, verbose_name="Concurrency",
        help_text="Max requests processed in parallel.",
    )
    download_delay = models.FloatField(
        default=0.0, verbose_name="Delay",
        help_text="Seconds to wait between requests to the same site.",
    )

    # HTTP cache settings (map to Scrapy's HTTPCACHE_* options).
    cache_enabled = models.BooleanField(
        default=True, verbose_name="Enabled",
        help_text="Cache downloaded responses to disk and reuse them.",
    )
    cache_expiration_secs = models.PositiveIntegerField(
        default=0, verbose_name="Expiration",
        help_text="Seconds before a cached response expires (0 = never).",
    )
    cache_dir = models.CharField(
        max_length=255, default="httpcache", verbose_name="Directory",
        help_text="Folder where cached responses are stored.",
    )

    # LLM parsing.
    ollama_model = models.CharField(
        max_length=120, default="llama3.2", blank=True,
        help_text="Offline Ollama model used to parse pages into items.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Domain(models.Model):
    """An allowed domain and/or seed URL for a crawler.

    Maps to Scrapy's `allowed_domains` (host) and `start_urls` (start_url).
    """

    crawler = models.ForeignKey(
        Crawler, related_name="domains", on_delete=models.CASCADE
    )
    host = models.CharField(max_length=255, help_text="e.g. example.com")
    start_url = models.URLField(
        blank=True, help_text="Optional seed URL to begin crawling from"
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["host"]
        unique_together = ("crawler", "host")

    def __str__(self):
        return self.host


class Rule(models.Model):
    """A CrawlSpider link-following rule (Scrapy `Rule` + `LinkExtractor`)."""

    crawler = models.ForeignKey(
        Crawler, related_name="rules", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120, blank=True)

    # LinkExtractor parameters.
    allow = models.CharField(
        max_length=500, blank=True, help_text="Regex links must match"
    )
    deny = models.CharField(
        max_length=500, blank=True, help_text="Regex links must NOT match"
    )
    allow_domains = models.CharField(max_length=500, blank=True)
    deny_domains = models.CharField(max_length=500, blank=True)
    restrict_css = models.CharField(max_length=500, blank=True)
    restrict_xpaths = models.CharField(max_length=500, blank=True)

    # Rule parameters.
    callback = models.CharField(
        max_length=120, blank=True, help_text="Spider method to parse matched pages"
    )
    follow = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name or self.allow or f"rule#{self.pk}"


class Item(MPTTModel):
    """A scraped record produced by a crawler.

    Nestable so items can form a tree (e.g. a page and the pages it links to).
    """

    crawlers = models.ManyToManyField(
        Crawler, related_name="items", blank=True,
        help_text="The crawlers this item belongs to",
    )
    parent = TreeForeignKey(
        "self",
        related_name="children",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Broader item this one is nested under",
    )
    name = models.CharField(max_length=255, blank=True, help_text="Item title/label")
    label = models.CharField(max_length=255, blank=True)
    is_template = models.BooleanField(
        default=False, help_text="An extraction template (its Props drive parsing)"
    )
    rank = models.FloatField(default=0.0, db_index=True, help_text="Importance score")
    css = models.CharField(max_length=500, blank=True, help_text="Root CSS selector")
    xpath = models.CharField(max_length=500, blank=True, help_text="Root XPath expression")
    crawled_at = models.DateTimeField(auto_now_add=True)

    class MPTTMeta:
        order_insertion_by = ["name"]

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def save(self, *args, **kwargs):
        # Autopopulate label with the Title Case of name when not set.
        if self.name and not self.label:
            self.label = self.name.title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.label or f"item #{self.pk}"


class Prop(models.Model):
    """A property definition on an item (same shape as entity.Property)."""

    class DataType(models.TextChoices):
        STRING = "string", "String"
        INTEGER = "integer", "Integer"
        FLOAT = "float", "Float"
        BOOLEAN = "boolean", "Boolean"
        URL = "url", "URL"
        DATETIME = "datetime", "DateTime"
        JSON = "json", "JSON"

    item = models.ForeignKey(
        Item, related_name="props", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120)
    data_type = models.CharField(
        max_length=20, choices=DataType.choices, default=DataType.STRING
    )
    required = models.BooleanField(default=False)
    many = models.BooleanField(default=False, help_text="Holds a list of values")
    description = models.TextField(blank=True)
    # How to extract the value from a page.
    css = models.CharField(max_length=500, blank=True, help_text="CSS selector")
    xpath = models.CharField(max_length=500, blank=True, help_text="XPath expression")
    regex = models.CharField(max_length=500, blank=True, help_text="Regex pattern")

    class Meta:
        ordering = ["name"]
        unique_together = ("item", "name")

    def __str__(self):
        suffix = "[]" if self.many else ""
        return f"{self.name}: {self.data_type}{suffix}"
