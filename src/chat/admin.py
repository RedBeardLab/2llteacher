from django.contrib import admin

from .models import Chat, ChatMessage, ChatMessageContext


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "course", "is_deleted", "created_at"]
    list_filter = ["is_deleted", "course", "created_at"]
    search_fields = ["title", "user__username", "course__name"]


class ChatMessageContextInline(admin.TabularInline):
    model = ChatMessageContext
    fields = ["material_title", "page_start", "page_end", "score", "query"]
    readonly_fields = ["material_title", "page_start", "page_end", "score", "query"]
    can_delete = False
    extra = 0


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["chat", "message_type", "short_content", "timestamp"]
    list_filter = ["message_type", "timestamp"]
    search_fields = ["content", "chat__title"]
    inlines = [ChatMessageContextInline]
    readonly_fields = ["tool_call_id"]

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content


@admin.register(ChatMessageContext)
class ChatMessageContextAdmin(admin.ModelAdmin):
    list_display = ["message", "material_title", "page_start", "page_end", "score"]
    list_filter = ["material_title"]
    search_fields = ["material_title", "content", "query"]
