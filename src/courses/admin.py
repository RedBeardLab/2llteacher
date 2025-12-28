from django.contrib import admin
from .models import Course, CourseTeacher, CourseEnrollment, CourseHomework


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "created_at"]
    search_fields = ["name", "code"]
    list_filter = ["is_active", "created_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CourseTeacher)
class CourseTeacherAdmin(admin.ModelAdmin):
    list_display = ["course", "teacher", "role", "joined_at"]
    list_filter = ["role", "joined_at"]
    readonly_fields = ["joined_at"]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ["course", "student", "enrolled_at", "is_active"]
    list_filter = ["is_active", "enrolled_at"]
    readonly_fields = ["enrolled_at"]


@admin.register(CourseHomework)
class CourseHomeworkAdmin(admin.ModelAdmin):
    list_display = ["course", "homework", "assigned_at", "due_date"]
    list_filter = ["assigned_at"]
    readonly_fields = ["assigned_at"]
