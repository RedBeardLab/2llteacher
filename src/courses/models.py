import uuid
from typing import TYPE_CHECKING
from django.db import models

if TYPE_CHECKING:
    from accounts.models import Student, Teacher, TeacherAssistant


class Course(models.Model):
    """Represents a course that groups teachers, students, and homeworks"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=256, unique=True)

    # Many-to-many relationships
    teachers: "models.ManyToManyField[Teacher, CourseTeacher]" = models.ManyToManyField(
        "accounts.Teacher", through="CourseTeacher", related_name="courses"
    )
    students: "models.ManyToManyField[Student, CourseEnrollment]" = models.ManyToManyField(
        "accounts.Student", through="CourseEnrollment", related_name="enrolled_courses"
    )
    teacher_assistants: "models.ManyToManyField[TeacherAssistant, CourseTeacherAssistant]" = models.ManyToManyField(
        "accounts.TeacherAssistant",
        through="CourseTeacherAssistant",
        related_name="courses",
    )

    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses_course"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_active_students(self):
        """Returns queryset of active enrolled students"""
        return self.students.filter(courseenrollment__is_active=True)

    def get_teacher_role(self, teacher):
        """Get the role of a teacher in this course"""
        try:
            course_teacher = CourseTeacher.objects.get(course=self, teacher=teacher)
            return course_teacher.role
        except CourseTeacher.DoesNotExist:
            return None

    def is_teacher_owner(self, teacher):
        """Check if a teacher is the owner of this course"""
        return self.get_teacher_role(teacher) == "owner"

    def is_student_enrolled(self, student):
        """Check if a student is actively enrolled in this course"""
        return self.students.filter(
            id=student.id, courseenrollment__is_active=True
        ).exists()

    def is_teacher_assistant(self, teacher_assistant):
        """Check if a teacher assistant is assigned to this course"""
        return self.teacher_assistants.filter(
            id=teacher_assistant.id,
            courseteacherassistant__course=self,
        ).exists()

    def get_teacher_assistants_for_course(self):
        """Get all teacher assistants for this course"""
        return self.teacher_assistants.all()


class CourseTeacher(models.Model):
    """Through model for Course-Teacher relationship"""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("co_teacher", "Co-Teacher"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    teacher = models.ForeignKey("accounts.Teacher", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="co_teacher")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses_course_teacher"
        unique_together = [("course", "teacher")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.teacher.user.email} - {self.course.name} ({self.role})"


class CourseEnrollment(models.Model):
    """Through model for Course-Student relationship"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    student = models.ForeignKey("accounts.Student", on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "courses_course_enrollment"
        unique_together = [("course", "student")]
        ordering = ["-enrolled_at"]

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.student.user.email} - {self.course.name} ({status})"


class CourseTeacherAssistant(models.Model):
    """Through model for Course-TeacherAssistant relationship."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    teacher_assistant = models.ForeignKey(
        "accounts.TeacherAssistant", on_delete=models.CASCADE
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses_course_teacher_assistant"
        unique_together = [("course", "teacher_assistant")]
        ordering = ["assigned_at"]

    def __str__(self):
        return f"{self.teacher_assistant.user.email} - {self.course.name} (TA)"
