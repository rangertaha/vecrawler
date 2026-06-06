from django.contrib import admin
from django.db.models import JSONField
from django_json_widget.widgets import JSONEditorWidget

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "summary", "type", "created_at")
    list_filter = ("type",)
    autocomplete_fields = ("type",)
    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget},
    }

    @admin.display(description="title")
    def title(self, obj):
        return (obj.properties.get("title") if obj.properties else None) or "—"

    @admin.display(description="summary")
    def summary(self, obj):
        text = obj.properties.get("summary", "") if obj.properties else ""
        return (text[:120] + "…") if len(text) > 120 else (text or "—")
