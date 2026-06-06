"""Create config Items (+ Props) for common web-metadata standards.

    python manage.py createmetadata

Each standard becomes a crawler.Item whose Props define how to extract its
fields (via XPath). Idempotent — re-running updates the selectors in place.
"""

from django.core.management.base import BaseCommand

from crawler.models import Item, Prop

# Item name -> list of (prop name, xpath, data_type)
METADATA = {
    # Google rich results read HTML Microdata (itemscope/itemprop, schema.org).
    "Google Microdata": [
        ("itemtype", "//*[@itemscope][1]/@itemtype", Prop.DataType.URL),
        ("name", '//*[@itemprop="name"][1]//text()', Prop.DataType.STRING),
        ("description", '//*[@itemprop="description"][1]//text()', Prop.DataType.STRING),
        ("image", '//*[@itemprop="image"][1]/@src', Prop.DataType.URL),
        ("url", '//*[@itemprop="url"][1]/@href', Prop.DataType.URL),
        ("author", '//*[@itemprop="author"][1]//text()', Prop.DataType.STRING),
    ],
    "Facebook": [
        ("og:title", '//meta[@property="og:title"]/@content', Prop.DataType.STRING),
        ("og:description", '//meta[@property="og:description"]/@content', Prop.DataType.STRING),
        ("og:image", '//meta[@property="og:image"]/@content', Prop.DataType.URL),
        ("og:url", '//meta[@property="og:url"]/@content', Prop.DataType.URL),
        ("og:type", '//meta[@property="og:type"]/@content', Prop.DataType.STRING),
        ("og:site_name", '//meta[@property="og:site_name"]/@content', Prop.DataType.STRING),
    ],
    "Twitter": [
        ("twitter:card", '//meta[@name="twitter:card"]/@content', Prop.DataType.STRING),
        ("twitter:title", '//meta[@name="twitter:title"]/@content', Prop.DataType.STRING),
        ("twitter:description", '//meta[@name="twitter:description"]/@content', Prop.DataType.STRING),
        ("twitter:image", '//meta[@name="twitter:image"]/@content', Prop.DataType.URL),
        ("twitter:site", '//meta[@name="twitter:site"]/@content', Prop.DataType.STRING),
        ("twitter:creator", '//meta[@name="twitter:creator"]/@content', Prop.DataType.STRING),
    ],
    "Schema.org": [
        ("jsonld", '//script[@type="application/ld+json"]/text()', Prop.DataType.JSON),
        ("itemtype", "//*[@itemscope]/@itemtype", Prop.DataType.URL),
    ],
    "Dublin Core": [
        ("dc.title", '//meta[@name="DC.title"]/@content', Prop.DataType.STRING),
        ("dc.creator", '//meta[@name="DC.creator"]/@content', Prop.DataType.STRING),
        ("dc.subject", '//meta[@name="DC.subject"]/@content', Prop.DataType.STRING),
        ("dc.description", '//meta[@name="DC.description"]/@content', Prop.DataType.STRING),
        ("dc.publisher", '//meta[@name="DC.publisher"]/@content', Prop.DataType.STRING),
        ("dc.date", '//meta[@name="DC.date"]/@content', Prop.DataType.DATETIME),
    ],
}


class Command(BaseCommand):
    help = "Create config Items + Props for common web-metadata standards."

    def handle(self, *args, **options):
        items, props = 0, 0
        for item_name, fields in METADATA.items():
            item, created = Item.objects.get_or_create(
                name=item_name, defaults={"is_template": True}
            )
            if not item.is_template:
                item.is_template = True
                item.save(update_fields=["is_template"])
            items += created
            for field, xpath, data_type in fields:
                _, p_created = Prop.objects.update_or_create(
                    item=item,
                    name=field,
                    defaults={"xpath": xpath, "data_type": data_type},
                )
                props += p_created
            self.stdout.write(f"  {item_name}: {len(fields)} field(s)")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {items} new item(s); {props} new prop(s) "
                f"({len(METADATA)} metadata standard(s))."
            )
        )
