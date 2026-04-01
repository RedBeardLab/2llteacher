"""
Tests for the ConversationStartView.

This module tests the functionality for starting a new conversation on a section.
"""

from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from uuid import UUID
from datetime import timedelta
from django.utils import timezone

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section
from courses.models import Course


class ConversationStartViewTests(TestCase):
    """Test cases for the ConversationStartView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create a test user with teacher profile
        self.teacher_user = User.objects.create_user(
            username="teacheruser",
            email="teacher@example.com",
            first_name="Test",
            last_name="Teacher",
            password="password123",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create course for homework assignment
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create a test user with student profile
        self.student_user = User.objects.create_user(
            username="studentuser",
            email="student@example.com",
            first_name="Test",
            last_name="Student",
            password="password123",
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a test homework and section with due_date
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),  # Due in 7 days
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        # URL for starting a conversation on this section
        self.start_url = reverse(
            "conversations:start", kwargs={"section_id": self.section.id}
        )

    def test_conversation_start_requires_login(self):
        """Test that starting a conversation requires login."""
        response = self.client.get(self.start_url)

        # Check that the user is redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_student_can_view_start_form(self):
        """Test that a student can view the conversation start form."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Access the start conversation page
        response = self.client.get(self.start_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "conversations/start.html")

        # Check context data
        self.assertIsNotNone(response.context["view_data"])
        self.assertEqual(
            str(response.context["view_data"].section_id), str(self.section.id)
        )
        self.assertEqual(
            response.context["view_data"].section_title, self.section.title
        )
        self.assertEqual(
            str(response.context["view_data"].homework_id), str(self.homework.id)
        )
        self.assertEqual(
            response.context["view_data"].homework_title, self.homework.title
        )

    def test_teacher_can_view_start_form(self):
        """Test that a teacher can view the conversation start form."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Access the start conversation page
        response = self.client.get(self.start_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "conversations/start.html")

        # Check context data
        self.assertIsNotNone(response.context["view_data"])
        self.assertEqual(
            str(response.context["view_data"].section_id), str(self.section.id)
        )
        self.assertEqual(
            response.context["view_data"].section_title, self.section.title
        )

    @patch("conversations.services.ConversationService.start_conversation")
    def test_start_conversation_success(self, mock_start_conversation):
        """Test successful conversation creation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock the service response
        mock_conversation_id = UUID("12345678-1234-5678-1234-567812345678")
        mock_result = MagicMock(
            success=True,
            conversation_id=mock_conversation_id,
            section_id=self.section.id,
        )
        mock_start_conversation.return_value = mock_result

        # Submit the form
        response = self.client.post(self.start_url, {})

        # Check that the service was called correctly
        mock_start_conversation.assert_called_once()
        args = mock_start_conversation.call_args[0]
        self.assertEqual(args[0], self.student_user)
        self.assertEqual(args[1].id, self.section.id)

        # Check redirect to conversation detail
        self.assertEqual(response.status_code, 302)
        expected_url = reverse(
            "conversations:detail", kwargs={"conversation_id": mock_conversation_id}
        )
        self.assertEqual(response.url, expected_url)

    @patch("conversations.services.ConversationService.start_conversation")
    def test_start_conversation_error(self, mock_start_conversation):
        """Test error handling for conversation creation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock service error response
        mock_result = MagicMock(
            success=False,
            error="Error creating conversation",
            section_id=self.section.id,
        )
        mock_start_conversation.return_value = mock_result

        # Submit the form
        response = self.client.post(self.start_url, {})

        # Check that the form shows an error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Error creating conversation")

    def test_section_does_not_exist(self):
        """Test the view behavior when the section does not exist."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Create URL with non-existent section ID
        non_existent_url = reverse(
            "conversations:start",
            kwargs={"section_id": UUID("00000000-0000-0000-0000-000000000000")},
        )

        # Try to access the page
        response = self.client.get(non_existent_url)

        # Check response is a 404
        self.assertEqual(response.status_code, 404)

    def test_get_non_interactive_section_returns_403(self):
        """GET on a non-interactive section is forbidden — no LLM in the loop."""
        ni_section = Section.objects.create(
            homework=self.homework,
            title="Written Q",
            content="Explain X.",
            order=2,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )
        self.client.login(username="studentuser", password="password123")
        url = reverse("conversations:start", kwargs={"section_id": ni_section.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_post_non_interactive_section_returns_403(self):
        """POST on a non-interactive section is forbidden — no conversation created."""
        ni_section = Section.objects.create(
            homework=self.homework,
            title="Written Q",
            content="Explain X.",
            order=2,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )
        self.client.login(username="studentuser", password="password123")
        url = reverse("conversations:start", kwargs={"section_id": ni_section.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
