from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Conversation, Message, Submission, PasteEvent, RapidTextGrowthEvent


class MessageInline(admin.StackedInline):
    """Inline admin for displaying messages within a conversation."""

    model = Message
    extra = 0  # Don't show empty forms
    readonly_fields = ("id", "content", "message_type", "timestamp")
    fields = ("message_type", "content", "timestamp")
    ordering = ("timestamp",)

    def has_add_permission(self, request, obj=None):
        """Prevent adding new messages through admin to preserve conversation integrity."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting messages through admin to preserve conversation integrity."""
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model with inline messages."""

    list_display = (
        "id",
        "user_link",
        "section_link",
        "message_count",
        "is_teacher_test",
        "created_at",
        "is_deleted",
    )
    list_filter = ("is_deleted", "created_at")
    search_fields = ("user__username", "user__email", "section__title")
    readonly_fields = ("id", "created_at", "updated_at", "message_count")
    inlines = [MessageInline]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "user", "section")}),
        ("Status", {"fields": ("is_deleted", "deleted_at")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
        ("Statistics", {"fields": ("message_count",), "classes": ("collapse",)}),
    )

    @admin.display(description="User", ordering="user__username")
    def user_link(self, obj):
        """Create a clickable link to the user's admin page."""
        url = reverse("admin:accounts_user_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)

    @admin.display(description="Section", ordering="section__title")
    def section_link(self, obj):
        """Create a clickable link to the section's admin page."""
        url = reverse("admin:homeworks_section_change", args=[obj.section.pk])
        return format_html('<a href="{}">{}</a>', url, obj.section.title)

    @admin.display(description="Teacher Test", boolean=True)
    def is_teacher_test(self, obj):
        """Display whether this is a teacher test conversation."""
        return obj.is_teacher_test


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = (
        "id",
        "conversation",
        "message_type",
        "content_preview",
        "timestamp",
    )
    list_filter = ("message_type", "timestamp")
    search_fields = ("content", "conversation__user__username")
    readonly_fields = ("id", "timestamp")

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "conversation", "message_type", "timestamp")},
        ),
        ("Content", {"fields": ("content",)}),
    )

    @admin.display(description="Content Preview")
    def content_preview(self, obj):
        """Show a preview of the message content."""
        if len(obj.content) > 100:
            return obj.content[:100] + "..."
        return obj.content


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Admin interface for Submission model."""

    list_display = ("id", "student_username", "section_title", "submitted_at")
    list_filter = ("submitted_at",)
    search_fields = ("conversation__user__username", "conversation__section__title")
    readonly_fields = ("id", "submitted_at", "section", "student")

    fieldsets = (
        ("Basic Information", {"fields": ("id", "conversation", "submitted_at")}),
        (
            "Related Information",
            {"fields": ("section", "student"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Student")
    def student_username(self, obj):
        """Display the student's username."""
        return obj.conversation.user.username

    @admin.display(description="Section")
    def section_title(self, obj):
        """Display the section title."""
        return obj.conversation.section.title


@admin.register(PasteEvent)
class PasteEventAdmin(admin.ModelAdmin):
    """Admin interface for PasteEvent model."""

    list_display = (
        "id",
        "conversation_link",
        "user_link",
        "word_count",
        "content_length",
        "content_preview",
        "timestamp",
    )
    list_filter = ("timestamp", "word_count")
    search_fields = (
        "pasted_content",
        "last_message_before_paste__conversation__user__username",
    )
    readonly_fields = (
        "id",
        "last_message_before_paste",
        "pasted_content",
        "word_count",
        "content_length",
        "timestamp",
        "conversation_info",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "timestamp",
                    "word_count",
                    "content_length",
                )
            },
        ),
        (
            "Context",
            {
                "fields": (
                    "conversation_info",
                    "last_message_before_paste",
                )
            },
        ),
        ("Pasted Content", {"fields": ("pasted_content",)}),
    )

    @admin.display(description="Conversation")
    def conversation_link(self, obj):
        """Create a clickable link to the conversation's admin page."""
        if obj.conversation:
            url = reverse("admin:conversations_conversation_change", args=[obj.conversation.pk])
            return format_html('<a href="{}">{}</a>', url, str(obj.conversation.id)[:8])
        return "N/A"

    @admin.display(description="User")
    def user_link(self, obj):
        """Create a clickable link to the user's admin page."""
        if obj.conversation:
            url = reverse("admin:accounts_user_change", args=[obj.conversation.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.conversation.user.username)
        return "N/A"

    @admin.display(description="Content Preview")
    def content_preview(self, obj):
        """Show a preview of the pasted content."""
        if len(obj.pasted_content) > 50:
            return obj.pasted_content[:50] + "..."
        return obj.pasted_content

    @admin.display(description="Conversation Info")
    def conversation_info(self, obj):
        """Display additional conversation information."""
        if obj.conversation:
            return format_html(
                "<strong>User:</strong> {}<br><strong>Section:</strong> {}",
                obj.conversation.user.username,
                obj.conversation.section.title,
            )
        return "N/A"

    def has_add_permission(self, request):
        """Prevent manual addition of paste events through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of paste events for cleanup."""
        return True


@admin.register(RapidTextGrowthEvent)
class RapidTextGrowthEventAdmin(admin.ModelAdmin):
    """Admin interface for RapidTextGrowthEvent model."""

    list_display = (
        "id",
        "conversation_link",
        "user_link",
        "character_count",
        "content_preview",
        "timestamp",
    )
    list_filter = ("timestamp",)
    search_fields = (
        "added_text",
        "last_message_before_event__conversation__user__username",
    )
    readonly_fields = (
        "id",
        "last_message_before_event",
        "added_text",
        "timestamp",
        "conversation_info",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "timestamp",
                )
            },
        ),
        (
            "Context",
            {
                "fields": (
                    "conversation_info",
                    "last_message_before_event",
                )
            },
        ),
        ("Added Text", {"fields": ("added_text",)}),
    )

    @admin.display(description="Conversation")
    def conversation_link(self, obj):
        """Create a clickable link to the conversation's admin page."""
        if obj.conversation:
            url = reverse("admin:conversations_conversation_change", args=[obj.conversation.pk])
            return format_html('<a href="{}">{}</a>', url, str(obj.conversation.id)[:8])
        return "N/A"

    @admin.display(description="User")
    def user_link(self, obj):
        """Create a clickable link to the user's admin page."""
        if obj.conversation:
            url = reverse("admin:accounts_user_change", args=[obj.conversation.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.conversation.user.username)
        return "N/A"

    @admin.display(description="Characters")
    def character_count(self, obj):
        """Display the number of characters in the added text."""
        return len(obj.added_text)

    @admin.display(description="Content Preview")
    def content_preview(self, obj):
        """Show a preview of the added text."""
        if len(obj.added_text) > 50:
            return obj.added_text[:50] + "..."
        return obj.added_text

    @admin.display(description="Conversation Info")
    def conversation_info(self, obj):
        """Display additional conversation information."""
        if obj.conversation:
            return format_html(
                "<strong>User:</strong> {}<br><strong>Section:</strong> {}",
                obj.conversation.user.username,
                obj.conversation.section.title,
            )
        return "N/A"

    def has_add_permission(self, request):
        """Prevent manual addition of rapid text growth events through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of rapid text growth events for cleanup."""
        return True
