"""
Tests for the ConversationDeleteAndRestartView.
"""

from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils import timezone
from unittest.mock import patch, MagicMock

from accounts.models import Student, Teacher
from homeworks.models import Homework, Section
from courses.models import Course
from conversations.models import Conversation
from conversations.services import ConversationService

User = get_user_model()


class ConversationDeleteAndRestartViewTests(TestCase):
    """Test cases for the ConversationDeleteAndRestartView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test users
        self.student_user = User.objects.create_user(
            username="student1", email="student1@example.com", password="testpass123"
        )
        self.student_profile = Student.objects.create(user=self.student_user)

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher1@example.com", password="testpass123"
        )
        self.teacher_profile = Teacher.objects.create(user=self.teacher_user)

        # Create course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create test homework and section
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            due_date=timezone.now() + timedelta(days=365),
            created_by=self.teacher_profile,
            course=self.course,
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        # Create test conversation
        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

    def test_delete_and_restart_requires_login(self):
        """Test that deleting and restarting a conversation requires login."""
        url = reverse(
            "conversations:delete_and_restart",
            kwargs={"conversation_id": self.conversation.id},
        )
        response = self.client.post(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_student_can_delete_own_conversation(self):
        """Test that a student can delete and restart their own conversation."""
        self.client.login(username="student1", password="testpass123")

        # Mock the ConversationService.start_conversation method
        with patch.object(ConversationService, "start_conversation") as mock_start:
            # Mock successful conversation creation
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.conversation_id = "12345678-1234-1234-1234-123456789abc"
            mock_start.return_value = mock_result

            url = reverse(
                "conversations:delete_and_restart",
                kwargs={"conversation_id": self.conversation.id},
            )
            response = self.client.post(url)

            # Should redirect to new conversation
            self.assertEqual(response.status_code, 302)
            self.assertIn(
                "conversations/12345678-1234-1234-1234-123456789abc/",
                response["Location"],
            )

            # Check that the original conversation was soft deleted
            self.conversation.refresh_from_db()
            self.assertTrue(self.conversation.is_deleted)

            # Check success message
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            self.assertIn(
                "Previous conversation deleted and new one started", str(messages[0])
            )

    def test_student_cannot_delete_other_student_conversation(self):
        """Test that a student cannot delete another student's conversation."""
        # Create another student
        other_student_user = User.objects.create_user(
            username="student2", email="student2@example.com", password="testpass123"
        )
        Student.objects.create(user=other_student_user)

        self.client.login(username="student2", password="testpass123")

        url = reverse(
            "conversations:delete_and_restart",
            kwargs={"conversation_id": self.conversation.id},
        )
        response = self.client.post(url)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Check that conversation was not deleted
        self.conversation.refresh_from_db()
        self.assertFalse(self.conversation.is_deleted)

    def test_conversation_not_found(self):
        """Test handling when conversation does not exist."""
        self.client.login(username="student1", password="testpass123")

        # Use a non-existent conversation ID
        url = reverse(
            "conversations:delete_and_restart",
            kwargs={"conversation_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.post(url)

        # Should return 404
        self.assertEqual(response.status_code, 404)

    def test_service_error_handling(self):
        """Test handling when ConversationService fails to create new conversation."""
        self.client.login(username="student1", password="testpass123")

        # Mock the ConversationService.start_conversation method to fail
        with patch.object(ConversationService, "start_conversation") as mock_start:
            # Mock failed conversation creation
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.error = "Test error message"
            mock_start.return_value = mock_result

            url = reverse(
                "conversations:delete_and_restart",
                kwargs={"conversation_id": self.conversation.id},
            )
            response = self.client.post(url)

            # Should redirect to homework detail
            self.assertEqual(response.status_code, 302)
            self.assertIn(f"homeworks/{self.homework.id}/", response["Location"])

            # Check that the original conversation was still soft deleted
            self.conversation.refresh_from_db()
            self.assertTrue(self.conversation.is_deleted)

            # Check error message
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            self.assertIn(
                "Error starting new conversation: Test error message", str(messages[0])
            )

    def test_get_request_not_allowed(self):
        """Test that GET requests are not allowed for this view."""
        self.client.login(username="student1", password="testpass123")

        url = reverse(
            "conversations:delete_and_restart",
            kwargs={"conversation_id": self.conversation.id},
        )
        response = self.client.get(url)

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
