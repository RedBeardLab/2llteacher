"""
Tests for the MessageSendView.

This module tests the functionality for sending messages in a conversation.
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
from conversations.models import Conversation, Message


class MessageSendViewTests(TestCase):
    """Test cases for the MessageSendView."""

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

        # Create a test homework and section
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

        # Create a conversation for student
        self.student_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Create a conversation for teacher
        self.teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )

        # Add initial messages to conversations
        Message.objects.create(
            conversation=self.student_conversation,
            content="Initial AI message",
            message_type="ai",
        )

        Message.objects.create(
            conversation=self.teacher_conversation,
            content="Initial AI message",
            message_type="ai",
        )

        # URL for sending messages to student conversation
        self.student_message_url = reverse(
            "conversations:send_message",
            kwargs={"conversation_id": self.student_conversation.id},
        )

        # URL for sending messages to teacher conversation
        self.teacher_message_url = reverse(
            "conversations:send_message",
            kwargs={"conversation_id": self.teacher_conversation.id},
        )

    def test_message_send_requires_login(self):
        """Test that sending a message requires login."""
        response = self.client.post(
            self.student_message_url, {"content": "Test message"}
        )

        # Check that the user is redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_student_can_send_message_to_own_conversation(self):
        """Test that a student can send a message to their own conversation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Send a message
        with patch(
            "conversations.services.ConversationService.process_message"
        ) as mock_process_message:
            # Mock the service response
            mock_user_message_id = UUID("12345678-1234-5678-1234-567812345678")
            mock_ai_message_id = UUID("87654321-8765-4321-8765-432187654321")
            mock_result = MagicMock(
                success=True,
                user_message_id=mock_user_message_id,
                ai_message_id=mock_ai_message_id,
            )
            mock_process_message.return_value = mock_result

            # Send the message
            response = self.client.post(
                self.student_message_url, {"content": "Hello, this is a test message"}
            )

            # Check that the service was called correctly
            mock_process_message.assert_called_once()
            args, kwargs = mock_process_message.call_args
            self.assertEqual(args[0].conversation_id, self.student_conversation.id)
            self.assertEqual(args[0].content, "Hello, this is a test message")
            self.assertEqual(kwargs["streaming"], False)

            # Check redirect to conversation detail
            self.assertEqual(response.status_code, 302)
            expected_url = reverse(
                "conversations:detail",
                kwargs={"conversation_id": self.student_conversation.id},
            )
            self.assertEqual(response.url, expected_url)

    def test_student_cannot_send_message_to_teacher_conversation(self):
        """Test that a student cannot send a message to a teacher's conversation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Attempt to send a message to teacher's conversation
        response = self.client.post(
            self.teacher_message_url, {"content": "This should not be allowed"}
        )

        # Check that we get an error form response (new unified behavior)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "You don&#x27;t have permission to send messages in this conversation.",
        )

    def test_teacher_can_send_message_to_own_conversation(self):
        """Test that a teacher can send a message to their own conversation."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Send a message
        with patch(
            "conversations.services.ConversationService.process_message"
        ) as mock_process_message:
            # Mock the service response
            mock_user_message_id = UUID("12345678-1234-5678-1234-567812345678")
            mock_ai_message_id = UUID("87654321-8765-4321-8765-432187654321")
            mock_result = MagicMock(
                success=True,
                user_message_id=mock_user_message_id,
                ai_message_id=mock_ai_message_id,
            )
            mock_process_message.return_value = mock_result

            # Send the message
            response = self.client.post(
                self.teacher_message_url, {"content": "Teacher test message"}
            )

            # Check that the service was called correctly
            mock_process_message.assert_called_once()
            args, kwargs = mock_process_message.call_args
            self.assertEqual(args[0].conversation_id, self.teacher_conversation.id)
            self.assertEqual(args[0].content, "Teacher test message")
            self.assertEqual(kwargs["streaming"], False)

            # Check redirect to conversation detail
            self.assertEqual(response.status_code, 302)
            expected_url = reverse(
                "conversations:detail",
                kwargs={"conversation_id": self.teacher_conversation.id},
            )
            self.assertRedirects(response, expected_url)

    def test_teacher_cannot_send_message_to_student_conversation(self):
        """Test that a teacher cannot send a message to a student's conversation."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Attempt to send a message to student's conversation
        response = self.client.post(
            self.student_message_url, {"content": "This should not be allowed"}
        )

        # Check that we get an error form response (new unified behavior)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "You don&#x27;t have permission to send messages in this conversation.",
        )

    def test_send_message_with_empty_content(self):
        """Test sending a message with empty content."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Send an empty message
        response = self.client.post(self.student_message_url, {"content": ""})

        # Check that the form has an error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Message content is required.")

    @patch("conversations.services.ConversationService.process_message")
    def test_send_message_service_error(self, mock_process_message):
        """Test error handling when service fails."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock service error response
        mock_result = MagicMock(
            success=False, error="Unexpected response from service."
        )
        mock_process_message.return_value = mock_result

        # Send the message
        response = self.client.post(
            self.student_message_url, {"content": "This should fail"}
        )

        # Check that the form shows an error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unexpected response from service.")

    def test_conversation_does_not_exist(self):
        """Test the view behavior when the conversation does not exist."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Create URL with non-existent conversation ID
        non_existent_url = reverse(
            "conversations:send_message",
            kwargs={"conversation_id": UUID("00000000-0000-0000-0000-000000000000")},
        )

        # Try to send a message
        response = self.client.post(non_existent_url, {"content": "Should not work"})

        # Check that we get an error response (unified validation catches this)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "You don&#x27;t have permission to send messages in this conversation.",
        )

    def test_special_message_types(self):
        """Test sending messages with special types."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Send R code message
        with patch(
            "conversations.services.ConversationService.process_message"
        ) as mock_process_message:
            # Mock the service response
            mock_result = MagicMock(
                success=True,
                user_message_id=UUID("12345678-1234-5678-1234-567812345678"),
                ai_message_id=UUID("87654321-8765-4321-8765-432187654321"),
            )
            mock_process_message.return_value = mock_result

            # Send the message with r_code type
            response = self.client.post(
                self.student_message_url,
                {"content": 'print("Hello, R!")', "message_type": "code"},
            )

            # Check that the service was called with the correct message type
            mock_process_message.assert_called_once()
            args, kwargs = mock_process_message.call_args
            self.assertEqual(args[0].message_type, "code")
            self.assertEqual(kwargs["streaming"], False)

            # Check redirect
            self.assertEqual(response.status_code, 302)
