from django.contrib import admin
from .models import LLMConfig, GlobalLLMDefault


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "model_name", "course", "is_default", "is_active"]
    list_filter = ["is_default", "is_active", "course"]
    search_fields = ["name", "model_name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(GlobalLLMDefault)
class GlobalLLMDefaultAdmin(admin.ModelAdmin):
    list_display = ["name", "model_name", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "model_name"]
    readonly_fields = ["id", "created_at", "updated_at"]
