from django.contrib import admin
from django.http import HttpRequest
from .models import Homework, Section, SectionSolution
from .services import HomeworkService


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "homework_type",
        "due_date",
        "publish_at",
        "expires_at",
        "is_hidden",
        "accessible_to_students",
    )
    list_filter = ("homework_type", "is_hidden", "course")
    readonly_fields = ("accessible_to_students",)
    actions = ["publish_selected"]

    @admin.display(boolean=True, description="Accessible to students")
    def accessible_to_students(self, obj):
        return obj.is_accessible_to_students

    @admin.action(description="Publish selected homeworks")
    def publish_selected(self, request: HttpRequest, queryset):
        published = 0
        for homework in queryset:
            result = HomeworkService.publish_homework(homework.id)
            if result.success:
                published += 1
        self.message_user(request, f"{published} homework(s) published.")


admin.site.register(Section)
admin.site.register(SectionSolution)
