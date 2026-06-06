from django.db import models
from django.utils.text import slugify


class Pipeline(models.Model):
    """A named processing pipeline."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Transform(models.Model):
    """An ordered transform within a pipeline."""

    pipeline = models.ForeignKey(
        Pipeline, related_name="transforms", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0, help_text="Execution order")
    command = models.CharField(
        max_length=255, blank=True, help_text="Management command to run, e.g. 'computetopics'"
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("pipeline", "order")

    def __str__(self):
        return f"{self.order}. {self.name}"
