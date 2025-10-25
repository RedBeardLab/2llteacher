"""
Tests for the ConversationDetailView.

This module tests the functionality for viewing an existing conversation.
"""

from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from uuid import UUID
from datetime import timedelta
from django.utils import timezone

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section
from conversations.models import Conversation, Message


class ConversationDetailViewTests(TestCase):
    """Test cases for the ConversationDetailView."""

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

        # Create a test user with student profile
        self.student_user = User.objects.create_user(
            username="studentuser",
            email="student@example.com",
            first_name="Test",
            last_name="Student",
            password="password123",
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a test homework and section
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),  # Due in 7 days
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        # Create a conversation for student
        self.student_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Create a conversation for teacher
        self.teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )

        # Add some messages to conversations
        Message.objects.create(
            conversation=self.student_conversation,
            content="Initial AI message",
            message_type="ai",
        )

        Message.objects.create(
            conversation=self.student_conversation,
            content="Student question",
            message_type="student",
        )

        Message.objects.create(
            conversation=self.teacher_conversation,
            content="Initial AI message",
            message_type="ai",
        )

        # URL for viewing student conversation
        self.student_detail_url = reverse(
            "conversations:detail",
            kwargs={"conversation_id": self.student_conversation.id},
        )

        # URL for viewing teacher conversation
        self.teacher_detail_url = reverse(
            "conversations:detail",
            kwargs={"conversation_id": self.teacher_conversation.id},
        )

    def test_conversation_detail_requires_login(self):
        """Test that viewing a conversation requires login."""
        response = self.client.get(self.student_detail_url)

        # Check that the user is redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_student_can_view_own_conversation(self):
        """Test that a student can view their own conversation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Access the conversation page
        response = self.client.get(self.student_detail_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "conversations/detail.html")

        # Check context data
        self.assertIsNotNone(response.context["conversation_data"])
        self.assertEqual(
            str(response.context["conversation_data"].id),
            str(self.student_conversation.id),
        )
        self.assertEqual(len(response.context["conversation_data"].messages), 2)

    def test_student_cannot_view_teacher_conversation(self):
        """Test that a student cannot view a teacher's conversation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Attempt to access teacher's conversation
        response = self.client.get(self.teacher_detail_url)

        # Check access is denied
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_view_own_conversation(self):
        """Test that a teacher can view their own conversation."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Access the conversation page
        response = self.client.get(self.teacher_detail_url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "conversations/detail.html")

        # Check context data
        self.assertIsNotNone(response.context["conversation_data"])
        self.assertEqual(
            str(response.context["conversation_data"].id),
            str(self.teacher_conversation.id),
        )

    def test_teacher_can_view_student_conversation(self):
        """Test that a teacher can view a student's conversation."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Access student conversation page
        response = self.client.get(self.student_detail_url)

        # Check response is successful for teacher viewing student conversation
        self.assertEqual(response.status_code, 200)

    @patch("conversations.services.ConversationService.get_conversation_data")
    def test_get_conversation_data_error(self, mock_get_conversation_data):
        """Test handling of errors when retrieving conversation data."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock service returning None (conversation not found)
        mock_get_conversation_data.return_value = None

        # Access the conversation page
        response = self.client.get(self.student_detail_url)

        # Check response is 404
        self.assertEqual(response.status_code, 404)

    def test_conversation_does_not_exist(self):
        """Test the view behavior when the conversation does not exist."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Create URL with non-existent conversation ID
        non_existent_url = reverse(
            "conversations:detail",
            kwargs={"conversation_id": UUID("00000000-0000-0000-0000-000000000000")},
        )

        # Try to access the page
        response = self.client.get(non_existent_url)

        # Check response is a 404
        self.assertEqual(response.status_code, 404)
