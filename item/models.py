from django.db import models


class Item(models.Model):
    """A scraped item/record, optionally linked to its crawler config item."""

    properties = models.JSONField(default=dict, blank=True, help_text="Extracted fields")
    type = models.ForeignKey(
        "crawler.Item",
        related_name="items",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The crawler config item (type) this matches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.properties.get("title") or self.properties.get("url") or f"item #{self.pk}"
