"""
Permission decorators for view access control.

This module provides decorators to restrict view access based on user roles
and object ownership, following the testable-first architecture principles.
"""

from functools import wraps
from typing import Callable, Any, TypeVar, cast, Protocol, ParamSpec, Concatenate
from uuid import UUID

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from accounts.models import Teacher, Student

# Type alias for request.user which can be either authenticated or anonymous
RequestUser = AbstractBaseUser | AnonymousUser

# ParamSpec for preserving function signatures
P = ParamSpec("P")
R = TypeVar("R", bound=HttpResponse)

# Create a type variable for the view function
ViewFunc = TypeVar("ViewFunc", bound=Callable[..., HttpResponse])


class UserWithTeacher(Protocol):
    """Protocol for User with teacher_profile attribute."""

    teacher_profile: Teacher


class UserWithStudent(Protocol):
    """Protocol for User with student_profile attribute."""

    student_profile: Student


class TeacherRequest(HttpRequest):
    """Request type where user is guaranteed to have teacher_profile.

    Note: The user attribute override is intentional - the decorator guarantees
    this type narrowing at runtime. The type: ignore is necessary because mypy
    doesn't allow narrowing an attribute type in a subclass.
    """

    user: UserWithTeacher  # type: ignore[assignment]


class StudentRequest(HttpRequest):
    """Request type where user is guaranteed to have student_profile.

    Note: The user attribute override is intentional - the decorator guarantees
    this type narrowing at runtime. The type: ignore is necessary because mypy
    doesn't allow narrowing an attribute type in a subclass.
    """

    user: UserWithStudent  # type: ignore[assignment]


def get_teacher_or_student(user: RequestUser) -> tuple[Teacher | None, Student | None]:
    """
    Get teacher and student profiles from a user object.

    Args:
        user: User object

    Returns:
        Tuple of (teacher, student) - each may be None if not applicable
    """
    teacher = getattr(user, "teacher_profile", None)
    student = getattr(user, "student_profile", None)
    return teacher, student


def teacher_required(
    view_func: Callable[Concatenate[TeacherRequest, P], R],
) -> Callable[Concatenate[HttpRequest, P], R]:
    """
    Decorator to ensure user is a teacher and transform request type.

    The decorated view function receives TeacherRequest with guaranteed teacher_profile access.

    Args:
        view_func: View function that expects TeacherRequest

    Returns:
        Decorated function that accepts HttpRequest and checks teacher access
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> R:
        teacher, _ = get_teacher_or_student(request.user)
        if not teacher:
            return cast(R, HttpResponseForbidden("Teacher access required."))
        # Cast to TeacherRequest since we've verified teacher_profile exists
        return view_func(cast(TeacherRequest, request), *args, **kwargs)

    return wrapper


def student_required(
    view_func: Callable[Concatenate[StudentRequest, P], R],
) -> Callable[Concatenate[HttpRequest, P], R]:
    """
    Decorator to ensure user is a student and transform request type.

    The decorated view function receives StudentRequest with guaranteed student_profile access.

    Args:
        view_func: View function that expects StudentRequest

    Returns:
        Decorated function that accepts HttpRequest and checks student access
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> R:
        _, student = get_teacher_or_student(request.user)
        if not student:
            return cast(R, HttpResponseForbidden("Student access required."))
        # Cast to StudentRequest since we've verified student_profile exists
        return view_func(cast(StudentRequest, request), *args, **kwargs)

    return wrapper


def homework_owner_required(view_func: ViewFunc) -> ViewFunc:
    """
    Decorator to ensure teacher owns the homework.

    Args:
        view_func: View function to decorate

    Returns:
        Decorated function that checks if teacher owns homework
    """

    @wraps(view_func)
    def wrapper(
        request: HttpRequest, homework_id: UUID, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        from homeworks.models import Homework

        homework = get_object_or_404(Homework, id=homework_id)
        teacher, _ = get_teacher_or_student(request.user)

        if not teacher or homework.created_by != teacher:
            return HttpResponseForbidden("Access denied.")

        # Pass the homework object instead of homework_id
        return view_func(request, homework, *args, **kwargs)

    return cast(ViewFunc, wrapper)


def section_access_required(view_func: ViewFunc) -> ViewFunc:
    """
    Decorator to ensure user has access to section.

    Allows access if:
    1. User is a teacher who owns the homework containing the section
    2. User is a student (with any further access checking done in the view)

    Args:
        view_func: View function to decorate

    Returns:
        Decorated function that checks if user has access to section
    """

    @wraps(view_func)
    def wrapper(
        request: HttpRequest, section_id: UUID, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        from homeworks.models import Section

        section = get_object_or_404(Section, id=section_id)
        teacher, student = get_teacher_or_student(request.user)

        if teacher and section.homework.created_by == teacher:
            # Teacher owns the homework
            return view_func(request, section, *args, **kwargs)
        elif student:
            # Student access (additional checks may be done in view)
            return view_func(request, section, *args, **kwargs)
        else:
            return HttpResponseForbidden("Access denied.")

    return cast(ViewFunc, wrapper)


def conversation_access_required(view_func: ViewFunc) -> ViewFunc:
    """
    Decorator to ensure user has access to conversation.

    Allows access if:
    1. User owns the conversation
    2. User is a teacher who owns the homework containing the section

    Args:
        view_func: View function to decorate

    Returns:
        Decorated function that checks if user has access to conversation
    """

    @wraps(view_func)
    def wrapper(
        request: HttpRequest, conversation_id: UUID, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        from conversations.models import Conversation

        conversation = get_object_or_404(Conversation, id=conversation_id)
        teacher, _ = get_teacher_or_student(request.user)

        # User owns the conversation
        if conversation.user == request.user:
            return view_func(request, conversation, *args, **kwargs)

        # Teacher owns the homework containing the section
        if teacher and conversation.section.homework.created_by == teacher:
            return view_func(request, conversation, *args, **kwargs)

        return HttpResponseForbidden("Access denied.")

    return cast(ViewFunc, wrapper)


def submission_access_required(view_func: ViewFunc) -> ViewFunc:
    """
    Decorator to ensure user has access to submission.

    Allows access if:
    1. User is the student who submitted
    2. User is a teacher who owns the homework containing the section

    Args:
        view_func: View function to decorate

    Returns:
        Decorated function that checks if user has access to submission
    """

    @wraps(view_func)
    def wrapper(
        request: HttpRequest, submission_id: UUID, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        from conversations.models import Submission

        submission = get_object_or_404(Submission, id=submission_id)
        teacher, student = get_teacher_or_student(request.user)

        # Student who submitted
        if student and submission.conversation.user == request.user:
            return view_func(request, submission, *args, **kwargs)

        # Teacher who owns the homework
        homework = submission.conversation.section.homework
        if teacher and homework.created_by == teacher:
            return view_func(request, submission, *args, **kwargs)

        return HttpResponseForbidden("Access denied.")

    return cast(ViewFunc, wrapper)


def course_homework_access_required(view_func: ViewFunc) -> ViewFunc:
    """
    Decorator to ensure user has access to homework based on course enrollment.

    Allows access if:
    1. User is a teacher who owns the homework
    2. User is a student enrolled in the course that has the homework

    Args:
        view_func: View function to decorate

    Returns:
        Decorated function that checks if user has homework access
    """

    @wraps(view_func)
    def wrapper(
        request: HttpRequest, homework_id: UUID, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        from homeworks.models import Homework

        homework = get_object_or_404(Homework, id=homework_id)
        teacher, student = get_teacher_or_student(request.user)

        # Teachers who own the homework have access
        if teacher and homework.created_by == teacher:
            return view_func(request, homework_id, *args, **kwargs)

        # For students, check if they're enrolled in the course that has this homework
        if student:
            is_enrolled = homework.course.is_student_enrolled(student)
            if is_enrolled:
                return view_func(request, homework_id, *args, **kwargs)

        return HttpResponseForbidden(
            "Access denied. You are not enrolled in the course that has this homework."
        )

    return cast(ViewFunc, wrapper)
