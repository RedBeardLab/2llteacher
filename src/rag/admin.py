from django.contrib import admin

from .models import CourseMaterial, CourseMaterialBlob, CourseMaterialChunk


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "course",
        "processing_status",
        "pages",
        "size",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["course", "processing_status", "created_at"]
    search_fields = ["title", "original_filename", "checksum", "course__name"]
    readonly_fields = [
        "id",
        "checksum",
        "size",
        "processing_status",
        "error_message",
        "pages",
        "created_at",
        "updated_at",
    ]


@admin.register(CourseMaterialBlob)
class CourseMaterialBlobAdmin(admin.ModelAdmin):
    list_display = ["material"]
    search_fields = ["material__title", "material__original_filename"]


@admin.register(CourseMaterialChunk)
class CourseMaterialChunkAdmin(admin.ModelAdmin):
    list_display = [
        "material",
        "level",
        "chunk_index",
        "page_start",
        "page_end",
        "token_count",
        "created_at",
    ]
    list_filter = ["level", "material__course"]
    search_fields = ["content", "material__title"]
    readonly_fields = [
        "id",
        "material",
        "level",
        "chunk_index",
        "content",
        "page_start",
        "page_end",
        "embedding",
        "token_count",
        "created_at",
    ]
