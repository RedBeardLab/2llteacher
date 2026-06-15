from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import CanvasProfile, CanvasFileSync


@admin.register(CanvasProfile)
class CanvasProfileAdmin(admin.ModelAdmin):
    """Admin interface for CanvasProfile model."""

    list_display = [
        "user",
        "canvas_user_id",
        "has_token",
        "token_status",
        "created_at",
    ]
    list_filter = [
        "created_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "canvas_user_id",
    ]
    readonly_fields = [
        "id",
        "user",
        "canvas_user_id",
        "access_token",
        "refresh_token",
        "token_expires_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    @admin.display(description="Has Token", boolean=True)
    def has_token(self, obj):
        return bool(obj.access_token)

    @admin.display(description="Token Status")
    def token_status(self, obj):
        if not obj.access_token:
            return format_html('<span style="color: gray;">—</span>')
        if obj.token_expires_at and obj.token_expires_at < timezone.now():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')


@admin.register(CanvasFileSync)
class CanvasFileSyncAdmin(admin.ModelAdmin):
    """Admin interface for CanvasFileSync model."""

    list_display = [
        "display_name",
        "course",
        "size",
        "has_material",
        "created_at",
    ]
    list_filter = [
        "created_at",
    ]
    search_fields = [
        "display_name",
        "filename",
        "course__name",
        "course__code",
    ]
    readonly_fields = [
        "id",
        "course",
        "canvas_file_id",
        "display_name",
        "filename",
        "size",
        "checksum",
        "material",
        "created_at",
    ]
    ordering = ["-created_at"]

    @admin.display(description="Has Material", boolean=True)
    def has_material(self, obj):
        return obj.material_id is not None
