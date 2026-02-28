"""
Tests for the PasteLogView.

This module tests the functionality for logging paste detection events.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section
from courses.models import Course
from conversations.models import Conversation, Message, PasteEvent


class PasteLogViewTests(TestCase):
    """Test cases for the PasteLogView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create a test user with student profile
        self.student_user = User.objects.create_user(
            username="studentuser",
            email="student@example.com",
            first_name="Test",
            last_name="Student",
            password="password123",
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a teacher user
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

        # Create a homework assignment
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        # Create a section
        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        # Create a conversation
        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Create a message in the conversation
        self.message = Message.objects.create(
            conversation=self.conversation,
            content="This is a test message",
            message_type="student",
        )

    def test_log_paste_event_success(self):
        """Test successfully logging a paste event."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_paste", args=[self.conversation.id])
        data = {
            "pasted_content": "This is a long pasted content with many words",
            "word_count": 9,
            "content_length": 46,
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("paste_event_id", response_data)

        # Verify paste event was created
        paste_event = PasteEvent.objects.get(id=response_data["paste_event_id"])
        self.assertEqual(paste_event.pasted_content, data["pasted_content"])
        self.assertEqual(paste_event.word_count, data["word_count"])
        self.assertEqual(paste_event.content_length, data["content_length"])
        self.assertEqual(paste_event.last_message_before_paste, self.message)

    def test_log_paste_event_without_messages(self):
        """Test logging a paste event in a conversation without messages."""
        # Create a new conversation without messages
        new_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_paste", args=[new_conversation.id])
        data = {
            "pasted_content": "First paste in conversation",
            "word_count": 4,
            "content_length": 30,
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertTrue(response_data["success"])

        # Verify paste event was created with no linked message
        paste_event = PasteEvent.objects.get(id=response_data["paste_event_id"])
        self.assertIsNone(paste_event.last_message_before_paste)

    def test_log_paste_event_unauthorized(self):
        """Test logging a paste event in someone else's conversation."""
        self.client.login(username="teacheruser", password="password123")

        url = reverse("conversations:api_log_paste", args=[self.conversation.id])
        data = {
            "pasted_content": "Unauthorized paste",
            "word_count": 2,
            "content_length": 18,
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)

    def test_log_paste_event_not_logged_in(self):
        """Test logging a paste event without being logged in."""
        url = reverse("conversations:api_log_paste", args=[self.conversation.id])
        data = {
            "pasted_content": "Unauthenticated paste",
            "word_count": 2,
            "content_length": 21,
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        # Should redirect to login or return 302
        self.assertIn(response.status_code, [302, 403])

    def test_log_paste_event_invalid_json(self):
        """Test logging a paste event with invalid JSON."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_paste", args=[self.conversation.id])

        response = self.client.post(
            url, "invalid json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_log_paste_event_conversation_not_found(self):
        """Test logging a paste event for a non-existent conversation."""
        self.client.login(username="studentuser", password="password123")

        # Use a random UUID that doesn't exist
        fake_uuid = "12345678-1234-1234-1234-123456789012"
        url = reverse("conversations:api_log_paste", args=[fake_uuid])
        data = {
            "pasted_content": "Paste in non-existent conversation",
            "word_count": 5,
            "content_length": 37,
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)

    def test_multiple_paste_events(self):
        """Test logging multiple paste events in the same conversation."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_paste", args=[self.conversation.id])

        # Log first paste event
        data1 = {
            "pasted_content": "First paste content",
            "word_count": 3,
            "content_length": 19,
        }
        response1 = self.client.post(
            url, json.dumps(data1), content_type="application/json"
        )
        self.assertEqual(response1.status_code, 201)

        # Log second paste event
        data2 = {
            "pasted_content": "Second paste content with more words",
            "word_count": 6,
            "content_length": 36,
        }
        response2 = self.client.post(
            url, json.dumps(data2), content_type="application/json"
        )
        self.assertEqual(response2.status_code, 201)

        # Verify both events were created
        paste_events = PasteEvent.objects.filter(
            last_message_before_paste__conversation=self.conversation
        )
        self.assertEqual(paste_events.count(), 2)
