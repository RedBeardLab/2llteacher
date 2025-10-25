"""
Views for the accounts app.

This module provides views for user authentication and profile management,
following the testable-first architecture with typed data contracts.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

from django.views import View
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from datetime import datetime

from .forms import RegistrationForm, LoginForm, ProfileForm
from .models import Student, User
from .email_service import EmailVerificationService


@dataclass
class RegistrationFormData:
    """Data structure for the registration form view."""

    email: str
    password: str
    confirm_password: str
    errors: Dict[str, str] | None = None


@dataclass
class RegistrationResult:
    """Result of a registration attempt."""

    success: bool
    user_id: Optional[UUID] = None
    error: Optional[str] = None


@dataclass
class LoginFormData:
    """Data structure for the login form view."""

    username: str
    password: str
    next_url: Optional[str] = None
    errors: Dict[str, str] | None = None


@dataclass
class LoginResult:
    """Result of a login attempt."""

    success: bool
    redirect_url: str
    error: Optional[str] = None


@dataclass
class ProfileData:
    """Data structure for the profile management view."""

    user_id: UUID
    username: str
    email: str
    first_name: str
    last_name: str
    role: str  # 'teacher' or 'student'
    joined_date: datetime

    # Teacher-specific fields
    courses_created: int = 0

    # Student-specific fields
    submissions_count: int = 0
    completed_sections: int = 0


class UserRegistrationView(View):
    """View for user registration (teacher/student)."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display the registration form."""
        # Check if user is already logged in
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            # For testing purposes, avoid using a named URL that might not exist in test environment
            return redirect("/")

        # Create empty registration form
        form = RegistrationForm()

        # Render the form
        return render(request, "accounts/register.html", {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST requests to process registration form submission."""
        # Check if user is already logged in
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            # For testing purposes, avoid using a named URL that might not exist in test environment
            return redirect("/")

        # Process the form submission
        form = RegistrationForm(request.POST)

        if form.is_valid():
            result = self._register_user(form)

            if result.success:
                # Get the created user
                user = User.objects.get(id=result.user_id)

                # Send verification email
                email_result = EmailVerificationService.send_verification_email(
                    user, request
                )

                if email_result.success:
                    # Don't log the user in immediately - they need to verify email first
                    messages.success(
                        request,
                        "Registration successful! Please check your email to verify your account.",
                    )
                    return render(
                        request, "accounts/email_verification_sent.html", {"user": user}
                    )
                else:
                    # If email sending fails, still log them in but show a warning
                    login(request, user)
                    messages.warning(
                        request,
                        "Registration successful, but we couldn't send the verification email. You can resend it from your profile.",
                    )
                    return redirect("/")
            else:
                messages.error(
                    request, result.error or "Registration failed. Please try again."
                )

        # Render the form with errors
        return render(request, "accounts/register.html", {"form": form})

    def _register_user(self, form) -> RegistrationResult:
        """
        Process user registration, creating student profile.

        Args:
            form: Valid RegistrationForm instance

        Returns:
            RegistrationResult with success status and user ID or error
        """
        try:
            with transaction.atomic():
                # Create user account
                user = form.save()

                # Always create student profile for public registration
                Student.objects.create(user=user)

                # Set the backend for authentication
                user.backend = "django.contrib.auth.backends.ModelBackend"

                # Return success result
                return RegistrationResult(success=True, user_id=user.id)

        except Exception as e:
            # Handle any errors
            return RegistrationResult(success=False, error=str(e))


class UserLoginView(View):
    """View for user authentication."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display the login form."""
        # Check if user is already logged in
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            # For testing purposes, avoid using a named URL that might not exist in test environment
            return redirect("/")

        # Create login form
        form = LoginForm()

        # Get the next URL from query parameters if it exists
        next_url = request.GET.get("next", "/")

        # Render the form
        return render(
            request, "accounts/login.html", {"form": form, "next_url": next_url}
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST requests to process login form submission."""
        # Check if user is already logged in
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            # For testing purposes, avoid using a named URL that might not exist in test environment
            return redirect("/")

        # Process the form submission
        form = LoginForm(data=request.POST)

        # Get the next URL from the form
        next_url = request.POST.get("next", "/")

        if form.is_valid():
            # Get username and password
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            # Authenticate user
            user = authenticate(username=username, password=password)

            if user is not None:
                # Log in the user
                login(request, user)
                messages.success(request, "You have successfully logged in.")

                # Redirect to the next URL or default
                return redirect(next_url)
            else:
                # This should not happen as form.is_valid() would have caught invalid credentials
                messages.error(request, "Invalid username or password.")

        # Render the form with errors
        return render(
            request, "accounts/login.html", {"form": form, "next_url": next_url}
        )


def logout_view(request):
    """View for logging out a user."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("/")


class ProfileManagementView(View):
    """View for viewing and editing user profiles."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests to display the profile form."""
        # Get user profile data
        profile_data = self._get_profile_data(request.user)

        # Create profile form with user instance
        form = ProfileForm(instance=request.user)

        # Render the form
        return render(
            request,
            "accounts/profile.html",
            {"form": form, "profile_data": profile_data},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST requests to process profile form submission."""
        # Create form with POST data and user instance
        form = ProfileForm(request.POST, instance=request.user)

        if form.is_valid():
            # Save the form
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")

        # Get user profile data
        profile_data = self._get_profile_data(request.user)

        # Render the form with errors
        return render(
            request,
            "accounts/profile.html",
            {"form": form, "profile_data": profile_data},
        )

    def _get_profile_data(self, user) -> ProfileData:
        """
        Get profile data for the user.

        Args:
            user: The current user

        Returns:
            ProfileData with user profile information
        """
        # Determine user role
        teacher_profile = getattr(user, "teacher_profile", None)
        student_profile = getattr(user, "student_profile", None)

        # Set role and role-specific data
        if teacher_profile:
            role = "teacher"
            courses_created = self._get_courses_count(teacher_profile)
            submissions_count = 0
            completed_sections = 0
        elif student_profile:
            role = "student"
            courses_created = 0
            submissions_count = self._get_submissions_count(student_profile)
            completed_sections = self._get_completed_sections_count(student_profile)
        else:
            role = "unknown"
            courses_created = 0
            submissions_count = 0
            completed_sections = 0

        # Create and return profile data
        return ProfileData(
            user_id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=role,
            joined_date=user.date_joined,
            courses_created=courses_created,
            submissions_count=submissions_count,
            completed_sections=completed_sections,
        )

    def _get_courses_count(self, teacher_profile) -> int:
        """
        Get the number of courses (homeworks) created by a teacher.

        Args:
            teacher_profile: Teacher profile object

        Returns:
            Integer count of courses created
        """
        return teacher_profile.homeworks_created.count()

    def _get_submissions_count(self, student_profile) -> int:
        """
        Get the number of submissions made by a student.

        Args:
            student_profile: Student profile object

        Returns:
            Integer count of submissions made
        """
        # In a real implementation, we would query the submissions table
        # Since we don't have direct access to it in the accounts app, we'll use 0 as a placeholder
        return 0

    def _get_completed_sections_count(self, student_profile) -> int:
        """
        Get the number of sections completed by a student.

        Args:
            student_profile: Student profile object

        Returns:
            Integer count of completed sections
        """
        # In a real implementation, we would query the submissions table
        # Since we don't have direct access to it in the accounts app, we'll use 0 as a placeholder
        return 0


class EmailVerificationView(View):
    """View for handling email verification links."""

    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        """Handle email verification token."""
        # Verify the token
        result = EmailVerificationService.verify_email_token(token)

        if result.success:
            messages.success(request, "Your email has been successfully verified!")
            return render(request, "accounts/email_verified.html")
        else:
            messages.error(request, result.error or "Email verification failed.")
            return render(
                request, "accounts/email_verified.html", {"error": result.error}
            )


class ResendVerificationView(View):
    """View for resending email verification."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET request to resend verification email."""
        # Cast user to our custom User model
        user = User.objects.get(pk=request.user.pk)

        # Check if user is already verified
        if user.is_email_verified:
            messages.info(request, "Your email is already verified.")
            return redirect("accounts:profile")

        # Resend verification email
        result = EmailVerificationService.resend_verification_email(user, request)

        if result.success:
            messages.success(
                request, "Verification email has been resent. Please check your inbox."
            )
        else:
            messages.error(
                request, result.error or "Failed to send verification email."
            )

        return render(request, "accounts/email_verification_sent.html")

    def _get_completed_sections_count(self, student_profile) -> int:
        """
        Get the number of sections completed by a student.

        Args:
            student_profile: Student profile object

        Returns:
            Integer count of completed sections
        """
        # In a real implementation, we would query the submissions table
        # Since we don't have direct access to it in the accounts app, we'll use 0 as a placeholder
        return 0
