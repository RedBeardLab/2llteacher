"""
Tests for the ProfileManagementView.

This module tests the user profile management functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch

from accounts.models import User, Teacher, Student


class ProfileManagementViewTests(TestCase):
    """Test cases for the ProfileManagementView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.profile_url = reverse("accounts:profile")

        # Create a test user with teacher profile
        self.teacher_user = User.objects.create_user(
            username="teacheruser",
            email="teacher@example.com",
            first_name="Test",
            last_name="Teacher",
            password="password123",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create a test user with student profile
        self.student_user = User.objects.create_user(
            username="studentuser",
            email="student@example.com",
            first_name="Test",
            last_name="Student",
            password="password123",
        )
        self.student = Student.objects.create(user=self.student_user)

    def test_profile_page_requires_login(self):
        """Test that the profile page requires login."""
        response = self.client.get(self.profile_url)

        # Check that the user is redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_teacher_profile_page_loads(self):
        """Test that the teacher profile page loads correctly."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Access profile page
        response = self.client.get(self.profile_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

        # Check context data
        self.assertIsNotNone(response.context["form"])
        self.assertIsNotNone(response.context["profile_data"])
        self.assertEqual(response.context["profile_data"].username, "teacheruser")
        self.assertEqual(response.context["profile_data"].role, "teacher")

    def test_student_profile_page_loads(self):
        """Test that the student profile page loads correctly."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Access profile page
        response = self.client.get(self.profile_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

        # Check context data
        self.assertIsNotNone(response.context["form"])
        self.assertIsNotNone(response.context["profile_data"])
        self.assertEqual(response.context["profile_data"].username, "studentuser")
        self.assertEqual(response.context["profile_data"].role, "student")

    def test_profile_update_success(self):
        """Test successful profile update."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Prepare update data
        data = {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.com",
        }

        # Submit the form
        response = self.client.post(self.profile_url, data)

        # Check that the user is redirected back to profile
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.profile_url)

        # Check that the user data was updated
        user = User.objects.get(username="teacheruser")
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.last_name, "Name")
        self.assertEqual(user.email, "updated@example.com")

    def test_profile_update_with_existing_email(self):
        """Test profile update with an email that already exists."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Prepare update data with student's email
        data = {
            "first_name": "Test",
            "last_name": "Teacher",
            "email": "student@example.com",  # This email is already used by the student
        }

        # Submit the form
        response = self.client.post(self.profile_url, data)

        # Check that the form has an error
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("email", response.context["form"].errors)

        # Check that the user data was not updated
        user = User.objects.get(username="teacheruser")
        self.assertNotEqual(user.email, "student@example.com")

    @patch("accounts.views.ProfileManagementView._get_courses_count")
    def test_teacher_stats_calculation(self, mock_get_courses_count):
        """Test teacher statistics are calculated correctly."""
        # Mock the courses count method
        mock_get_courses_count.return_value = 5

        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Access profile page
        response = self.client.get(self.profile_url)

        # Check that the stats are correct
        profile_data = response.context["profile_data"]
        self.assertEqual(profile_data.courses_created, 5)
        self.assertEqual(
            profile_data.submissions_count, 0
        )  # Teachers don't have submissions
        self.assertEqual(
            profile_data.completed_sections, 0
        )  # Teachers don't have completed sections

        # Verify mock was called
        mock_get_courses_count.assert_called_once()

    @patch("accounts.views.ProfileManagementView._get_submissions_count")
    @patch("accounts.views.ProfileManagementView._get_completed_sections_count")
    def test_student_stats_calculation(
        self, mock_sections_count, mock_submissions_count
    ):
        """Test student statistics are calculated correctly."""
        # Mock the stats methods
        mock_submissions_count.return_value = 10
        mock_sections_count.return_value = 15

        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Access profile page
        response = self.client.get(self.profile_url)

        # Check that the stats are correct
        profile_data = response.context["profile_data"]
        self.assertEqual(
            profile_data.courses_created, 0
        )  # Students don't create courses
        self.assertEqual(profile_data.submissions_count, 10)
        self.assertEqual(profile_data.completed_sections, 15)

        # Verify mocks were called
        mock_submissions_count.assert_called_once()
        mock_sections_count.assert_called_once()
