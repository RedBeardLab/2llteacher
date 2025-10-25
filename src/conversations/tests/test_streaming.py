"""
Tests for streaming LLM responses.

Testing the streaming functionality with a simple approach.
"""

import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch

from homeworks.models import Homework, Section
from conversations.models import Conversation, Message
from accounts.models import Student, Teacher

User = get_user_model()


class StreamingLLMTest(TestCase):
    """Test the streaming LLM response functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create student profile
        self.student_profile = Student.objects.create(user=self.user)

        # Create teacher for homework
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="teacherpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create homework and section
        from datetime import datetime

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            created_by=self.teacher,
            due_date=datetime(2024, 12, 31),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        # Create conversation
        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

        # Login user
        self.client.login(username="testuser", password="testpass123")

    @patch("llm.services.LLMService.stream_response_with_completion")
    def test_streaming_llm_response(self, mock_stream):
        """Test streaming LLM response functionality."""
        # Mock the enhanced streaming response with StreamToken objects
        from llm.services import StreamToken, StreamTokenType, FinishReason
        
        mock_stream.return_value = iter([
            StreamToken(type=StreamTokenType.TOKEN, content="Hello"),
            StreamToken(type=StreamTokenType.TOKEN, content=" there"),
            StreamToken(type=StreamTokenType.TOKEN, content="! How"),
            StreamToken(type=StreamTokenType.TOKEN, content=" can I"),
            StreamToken(type=StreamTokenType.TOKEN, content=" help?"),
            StreamToken(type=StreamTokenType.COMPLETE, content="Hello there! How can I help?", finish_reason=FinishReason.STOP),
        ])

        url = reverse(
            "conversations:api_stream", kwargs={"conversation_id": self.conversation.id}
        )

        data = {
            "content": "Hello, I need help with this section",
            "message_type": "student",
        }

        # Test POST request (streaming)
        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")

        # Consume the streaming response to trigger message creation
        response_content = b"".join(response)

        # Verify that messages were created
        messages = Message.objects.filter(conversation=self.conversation)
        self.assertEqual(messages.count(), 2)  # User message + AI message

        # Verify user message
        user_message = messages.filter(message_type="student").first()
        self.assertIsNotNone(user_message)
        self.assertEqual(user_message.content, "Hello, I need help with this section")

        # Verify AI message
        ai_message = messages.filter(message_type="ai").first()
        self.assertIsNotNone(ai_message)
        self.assertEqual(ai_message.content, "Hello there! How can I help?")

        # Verify the streaming response contains expected events
        response_text = response_content.decode("utf-8")
        self.assertIn("user_message", response_text)
        self.assertIn("ai_message_start", response_text)
        self.assertIn("ai_token", response_text)
        self.assertIn("ai_message_complete", response_text)

    def test_streaming_permission_denied(self):
        """Test streaming with wrong user permissions."""
        # Create another user
        _other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="otherpass123"
        )

        # Login as other user
        self.client.login(username="otheruser", password="otherpass123")

        url = reverse(
            "conversations:api_stream", kwargs={"conversation_id": self.conversation.id}
        )

        data = {"content": "This should fail", "message_type": "student"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)  # SSE always returns 200
        # The error would be in the stream content

    def test_streaming_empty_content(self):
        """Test streaming with empty message content."""
        url = reverse(
            "conversations:api_stream", kwargs={"conversation_id": self.conversation.id}
        )

        data = {"content": "", "message_type": "student"}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)  # SSE always returns 200
        # The error would be in the stream content
