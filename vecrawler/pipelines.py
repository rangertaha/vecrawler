# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


def _setup_django():
    """Boot the Django ORM inside the Scrapy process (idempotent)."""
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Scrapy 2.13 runs on the asyncio reactor; allow synchronous ORM calls
    # from within that running event loop.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    django.setup()


class CleanFieldsPipeline:
    """Normalize scraped values: strip whitespace from all string fields."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        for field, value in adapter.items():
            if isinstance(value, str):
                adapter[field] = value.strip()
        return item


class DuplicatesPipeline:
    """Drop items already seen this run, keyed on the item's `url` field.

    Falls through (keeps the item) if there's no `url` field to key on.
    """

    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get("url")
        if url is None:
            return item
        if url in self.seen_urls:
            raise DropItem(f"Duplicate item dropped: {url}")
        self.seen_urls.add(url)
        return item


class ItemSaverPipeline:
    """Parse each scraped page with a local Ollama model and save an item.Item.

    The page content is sent to an offline Ollama model, which returns a JSON
    object of structured fields (title/summary/image/topics). If Ollama is
    unreachable, the item is still saved from the raw scraped data.

    Config via env vars: OLLAMA_HOST (default http://localhost:11434),
    OLLAMA_MODEL (default llama3.2).
    """

    def open_spider(self, spider):
        _setup_django()
        import os
        from item.models import Item

        self.Item = Item
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        # Per-crawler model (config-driven spiders expose `spider.config`);
        # fall back to the OLLAMA_MODEL env var, then a default.
        cfg = getattr(spider, "config", None)
        self.model = (
            (cfg.ollama_model if cfg and cfg.ollama_model else None)
            or os.environ.get("OLLAMA_MODEL", "llama3.2")
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = dict(adapter)
        content = data.pop("content", "")  # don't persist the raw blob

        parsed = self._ollama_parse(content, data.get("url", ""), spider)

        # All scraped + LLM-parsed fields are stored in `properties`.
        self.Item.objects.create(properties={**data, **parsed})
        return item

    def _ollama_parse(self, content, url, spider):
        """Ask the local Ollama model to extract structured fields as JSON."""
        if not content:
            return {}
        import json
        import urllib.request

        prompt = (
            "Extract structured data from this web page. Respond ONLY with a "
            "JSON object with keys: title (string), summary (string, 1-2 "
            "sentences), image (string url or empty), topics (list of strings).\n"
            f"URL: {url}\n\nPAGE CONTENT:\n{content}"
        )
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(body.get("response", "{}"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception as exc:  # Ollama down / model missing / bad JSON
            spider.logger.warning("Ollama parse failed (%s); saving raw data", exc)
            return {}


class VecrawlerPipeline:
    def process_item(self, item, spider):
        return item
