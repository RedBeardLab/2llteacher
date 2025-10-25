"""
Tests for the UserRegistrationView.

This module tests the user registration functionality for both teacher and student roles.
"""

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User


class UserRegistrationViewTests(TestCase):
    """Test cases for the UserRegistrationView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.register_url = reverse("accounts:register")

        # Create an existing user for duplicate tests
        self.existing_user = User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="password123",
        )

    def test_registration_page_loads(self):
        """Test that the registration page loads correctly."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")
        self.assertIsNotNone(response.context["form"])

    def test_register_student_success(self):
        """Test successful student registration."""

        data = {
            "email": "student@uw.edu",
            "first_name": "Test",
            "last_name": "Student",
            "password1": "complex-password-123",
            "password2": "complex-password-123",
        }

        response = self.client.post(self.register_url, data)

        # Check that the user was created with email as username
        self.assertTrue(User.objects.filter(username="student@uw.edu").exists())
        user = User.objects.get(username="student@uw.edu")

        # Check that the student profile was created
        self.assertTrue(hasattr(user, "student_profile"))
        self.assertIsNotNone(user.student_profile)

        # Check that user is not email verified initially
        self.assertFalse(user.is_email_verified)

        # Check that email verification sent template is rendered
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verification_sent.html")
        self.assertEqual(response.context["user"], user)

    def test_register_with_duplicate_email(self):
        """Test registration with a duplicate email fails."""
        data = {
            "email": "existing@example.com",  # Already exists
            "first_name": "Test",
            "last_name": "User",
            "password1": "complex-password-123",
            "password2": "complex-password-123",
        }

        response = self.client.post(self.register_url, data)

        # Check that the form has an error
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("email", response.context["form"].errors)

        # Check that no new user was created
        self.assertEqual(User.objects.count(), 1)  # Only the existing user

    def test_register_with_password_mismatch(self):
        """Test registration with mismatched passwords fails."""
        data = {
            "email": "new@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password1": "complex-password-123",
            "password2": "different-password",  # Doesn't match
        }

        response = self.client.post(self.register_url, data)

        # Check that the form has an error
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("password2", response.context["form"].errors)

        # Check that no new user was created
        self.assertEqual(User.objects.count(), 1)  # Only the existing user

    def test_already_authenticated_redirect(self):
        """Test that authenticated users are redirected."""

        # Create and log in a user
        user = User.objects.create_user(username="loggedinuser", password="password123")
        self.client.force_login(user)

        # Try to access the registration page
        response = self.client.get(self.register_url)

        # Check that the user is redirected
        self.assertEqual(response.status_code, 302)

        # Test POST request while logged in
        data = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password1": "complex-password-123",
            "password2": "complex-password-123",
        }

        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 302)

        # Check that no new user was created
        self.assertFalse(User.objects.filter(username="test@example.com").exists())
