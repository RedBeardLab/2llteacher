from enum import StrEnum


class CourseRole(StrEnum):
    """Enumeration of possible user roles within a course context."""

    TEACHER = "teacher"
    STUDENT = "student"
    TEACHER_ASSISTANT = "teacher_assistant"
