from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Teacher, Student, EmailVerification


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    """Admin interface for EmailVerification model."""
    
    list_display = [
        'user',
        'token_short',
        'created_at',
        'expires_at',
        'status',
        'is_expired_display',
    ]
    list_filter = [
        'is_used',
        'created_at',
        'expires_at',
    ]
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'token',
    ]
    readonly_fields = [
        'id',
        'token',
        'created_at',
        'is_expired_display',
        'is_valid_display',
    ]
    ordering = ['-created_at']
    
    @admin.display(description="Token")
    def token_short(self, obj):
        """Display shortened token for readability."""
        return f"{obj.token[:8]}...{obj.token[-8:]}"
    
    @admin.display(description="Status")
    def status(self, obj):
        """Display verification status with color coding."""
        if obj.is_used:
            return format_html('<span style="color: green;">✓ Used</span>')
        elif obj.is_expired():
            return format_html('<span style="color: red;">✗ Expired</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
    
    @admin.display(description="Expired", boolean=True)
    def is_expired_display(self, obj):
        """Display expiration status."""
        return obj.is_expired()
    
    @admin.display(description="Valid", boolean=True)
    def is_valid_display(self, obj):
        """Display validity status."""
        return obj.is_valid()
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


admin.site.register(User, UserAdmin)
admin.site.register(Teacher)
admin.site.register(Student)
