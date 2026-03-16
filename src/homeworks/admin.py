from django.contrib import admin
from .models import Homework, Section, SectionSolution


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "due_date", "expires_at", "is_hidden", "accessible_to_students")
    list_filter = ("is_hidden", "course")
    readonly_fields = ("accessible_to_students",)

    @admin.display(boolean=True, description="Accessible to students")
    def accessible_to_students(self, obj):
        return obj.is_accessible_to_students


admin.site.register(Section)
admin.site.register(SectionSolution)
