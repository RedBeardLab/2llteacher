"""
Tests for the UserLoginView.

This module tests the user login functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, Teacher


class UserLoginViewTests(TestCase):
    """Test cases for the UserLoginView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.login_url = reverse("accounts:login")

        # Create a test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )

        # Create a teacher profile for the test user
        self.teacher = Teacher.objects.create(user=self.user)

    def test_login_page_loads(self):
        """Test that the login page loads correctly."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertIsNotNone(response.context["form"])
        self.assertIn("next_url", response.context)

    def test_login_success(self):
        """Test successful login."""
        data = {"username": "testuser", "password": "password123"}

        response = self.client.post(self.login_url, data)

        # Check that the user was redirected
        self.assertEqual(response.status_code, 302)

        # Check that the user is now authenticated
        user = response.wsgi_request.user
        self.assertTrue(user.is_authenticated)
        self.assertEqual(user.username, "testuser")

    def test_login_with_next_url(self):
        """Test login with a next URL parameter."""
        next_url = "/homeworks/"

        data = {"username": "testuser", "password": "password123", "next": next_url}

        response = self.client.post(self.login_url, data)

        # Check that the user was redirected to the next URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        data = {"username": "testuser", "password": "wrongpassword"}

        response = self.client.post(self.login_url, data)

        # Check that the form has an error
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

        # Check that the user is still anonymous
        user = response.wsgi_request.user
        self.assertFalse(user.is_authenticated)

    def test_login_with_nonexistent_user(self):
        """Test login with a nonexistent username."""
        data = {"username": "nonexistentuser", "password": "password123"}

        response = self.client.post(self.login_url, data)

        # Check that the form has an error
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

        # Check that the user is still anonymous
        user = response.wsgi_request.user
        self.assertFalse(user.is_authenticated)

    def test_already_authenticated_redirect(self):
        """Test that authenticated users are redirected."""
        # Log in the user
        self.client.force_login(self.user)

        # Try to access the login page
        response = self.client.get(self.login_url)

        # Check that the user is redirected
        self.assertEqual(response.status_code, 302)

        # Test POST request while logged in
        data = {"username": "testuser", "password": "password123"}

        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 302)
