from django.contrib import admin

from .models import CourseMaterial, CourseMaterialBlob


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "course",
        "original_filename",
        "size",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["course", "content_type", "created_at"]
    search_fields = ["title", "original_filename", "checksum", "course__name"]
    readonly_fields = ["id", "checksum", "size", "created_at", "updated_at"]


@admin.register(CourseMaterialBlob)
class CourseMaterialBlobAdmin(admin.ModelAdmin):
    list_display = ["material"]
    search_fields = ["material__title", "material__original_filename"]
