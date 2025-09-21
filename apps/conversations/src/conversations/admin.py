from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Conversation, Message, Submission


class MessageInline(admin.StackedInline):
    """Inline admin for displaying messages within a conversation."""
    
    model = Message
    extra = 0  # Don't show empty forms
    readonly_fields = ('id', 'content', 'message_type', 'timestamp')
    fields = ('message_type', 'content', 'timestamp')
    ordering = ('timestamp',)
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding new messages through admin to preserve conversation integrity."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting messages through admin to preserve conversation integrity."""
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model with inline messages."""
    
    list_display = ('id', 'user_link', 'section_link', 'message_count', 'is_teacher_test', 'created_at', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('user__username', 'user__email', 'section__title')
    readonly_fields = ('id', 'created_at', 'updated_at', 'message_count')
    inlines = [MessageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'section')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('message_count',),
            'classes': ('collapse',)
        })
    )
    
    def user_link(self, obj):
        """Create a clickable link to the user's admin page."""
        url = reverse('admin:accounts_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def section_link(self, obj):
        """Create a clickable link to the section's admin page."""
        url = reverse('admin:homeworks_section_change', args=[obj.section.pk])
        return format_html('<a href="{}">{}</a>', url, obj.section.title)
    section_link.short_description = 'Section'
    section_link.admin_order_field = 'section__title'
    
    def is_teacher_test(self, obj):
        """Display whether this is a teacher test conversation."""
        return obj.is_teacher_test
    is_teacher_test.boolean = True
    is_teacher_test.short_description = 'Teacher Test'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""
    
    list_display = ('id', 'conversation', 'message_type', 'content_preview', 'timestamp')
    list_filter = ('message_type', 'timestamp')
    search_fields = ('content', 'conversation__user__username')
    readonly_fields = ('id', 'timestamp')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'message_type', 'timestamp')
        }),
        ('Content', {
            'fields': ('content',)
        })
    )
    
    def content_preview(self, obj):
        """Show a preview of the message content."""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Admin interface for Submission model."""
    
    list_display = ('id', 'student_username', 'section_title', 'submitted_at')
    list_filter = ('submitted_at',)
    search_fields = ('conversation__user__username', 'conversation__section__title')
    readonly_fields = ('id', 'submitted_at', 'section', 'student')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'submitted_at')
        }),
        ('Related Information', {
            'fields': ('section', 'student'),
            'classes': ('collapse',)
        })
    )
    
    def student_username(self, obj):
        """Display the student's username."""
        return obj.conversation.user.username
    student_username.short_description = 'Student'
    
    def section_title(self, obj):
        """Display the section title."""
        return obj.conversation.section.title
    section_title.short_description = 'Section'
