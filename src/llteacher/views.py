"""
Main views for the llteacher project.
"""

from django.shortcuts import render, redirect


def homepage(request):
    """
    Display the homepage with login form for unauthenticated users
    and welcome message for authenticated users.

    For students: Redirect to /courses/ if not enrolled in any course,
    otherwise redirect to /homeworks/
    """
    # Check if user is authenticated
    if request.user.is_authenticated:
        # Check if user is a student
        student_profile = getattr(request.user, "student_profile", None)
        if student_profile:
            # Check if student is enrolled in any courses
            from courses.models import CourseEnrollment
            has_enrollments = CourseEnrollment.objects.filter(
                student=student_profile, is_active=True
            ).exists()

            if has_enrollments:
                # Student has courses, redirect to homeworks
                return redirect("/homeworks/")
            else:
                # Student has no courses, redirect to course list
                return redirect("/courses/")

    return render(request, "homepage.html")
