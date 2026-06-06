from django.contrib import admin

from .models import Pipeline, Transform


class TransformInline(admin.TabularInline):
    model = Transform
    extra = 1


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "enabled", "created_at")
    list_filter = ("enabled",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [TransformInline]


@admin.register(Transform)
class TransformAdmin(admin.ModelAdmin):
    list_display = ("name", "pipeline", "order", "command", "enabled")
    list_filter = ("enabled", "pipeline")
    search_fields = ("name", "command")
