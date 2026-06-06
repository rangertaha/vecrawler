from django import forms
from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from mptt.admin import DraggableMPTTAdmin

from .models import (
    Crawler, Domain, Prop, Rule, Item,
)


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1
    # Plain text input for start_url (no "Currently:" clickable link).
    formfield_overrides = {
        models.URLField: {"widget": forms.URLInput(attrs={"size": 40})},
    }


class RuleInline(admin.TabularInline):
    model = Rule
    extra = 1


@admin.register(Crawler)
class CrawlerAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "enabled", "concurrent_requests", "download_delay", "cache_enabled")
    list_filter = ("enabled", "cache_enabled")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [DomainInline, RuleInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "enabled")}),
        ("Throttling", {"fields": ("concurrent_requests", "download_delay")}),
        ("Parsing", {"fields": ("ollama_model",)}),
        ("Cache settings", {
            "fields": ("cache_enabled", "cache_expiration_secs", "cache_dir"),
            "classes": ("collapse",),
        }),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("host", "crawler", "start_url", "enabled")
    list_filter = ("enabled", "crawler")
    search_fields = ("host", "start_url")


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "crawler", "allow", "deny", "callback", "follow")
    list_filter = ("follow", "crawler")


class PropInline(admin.TabularInline):
    model = Prop
    extra = 1
    # `description` is hidden in the Item inline only (still on PropAdmin).
    exclude = ("description",)


@admin.register(Item)
class ItemAdmin(DraggableMPTTAdmin):
    # Tree-indented changelist (table-based) so the standard "Delete selected"
    # action and per-row checkboxes are available, unlike the jqTree view.
    list_display = ("tree_actions", "indented_title", "label", "is_template", "crawler_list", "crawled_at", "delete_link")
    list_display_links = ("indented_title",)
    list_filter = ("is_template", "crawlers", "crawled_at")
    search_fields = ("name", "label")
    readonly_fields = ("crawled_at", "props_list")
    autocomplete_fields = ("parent", "crawlers")

    @admin.display(description="crawlers")
    def crawler_list(self, obj):
        return ", ".join(c.name for c in obj.crawlers.all()) or "—"

    @admin.display(description="")
    def delete_link(self, obj):
        url = reverse("admin:crawler_item_delete", args=[obj.pk])
        return format_html("<a class='deletelink' href='{}'>Delete</a>", url)

    @admin.display(description="props")
    def props_list(self, obj):
        """Links to edit each Prop on its own admin page (no inline)."""
        if not obj or not obj.pk:
            return "—"
        items = format_html_join(
            "",
            "<li><a href='{}'>{}</a></li>",
            (
                (reverse("admin:crawler_prop_change", args=[p.pk]), str(p))
                for p in obj.props.all()
            ),
        )
        add_url = reverse("admin:crawler_prop_add") + f"?item={obj.pk}"
        return format_html(
            "<ul style='margin:0 0 .5em;padding-left:1em'>{}</ul>"
            "<a class='addlink' href='{}'>Add prop</a>",
            items or format_html("<li>—</li>"),
            add_url,
        )


@admin.register(Prop)
class PropAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "data_type", "css", "xpath", "regex")
    list_filter = ("data_type", "required", "many")
    search_fields = ("name", "css", "xpath", "regex")
    autocomplete_fields = ("item",)
