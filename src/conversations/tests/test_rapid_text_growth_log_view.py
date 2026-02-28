"""
Tests for the RapidTextGrowthLogView.

This module tests the functionality for logging rapid text growth detection events.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section
from courses.models import Course
from conversations.models import Conversation, Message, RapidTextGrowthEvent


class RapidTextGrowthLogViewTests(TestCase):
    """Test cases for the RapidTextGrowthLogView."""

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

    def test_log_rapid_text_growth_event_success(self):
        """Test successfully logging a rapid text growth event."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_events", args=[self.conversation.id])
        data = {
            "added_text": "This is text that was added very quickly",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)

        # Verify rapid text growth event was created
        rapid_text_growth_event = RapidTextGrowthEvent.objects.get(
            last_message_before_event__conversation=self.conversation
        )
        self.assertEqual(rapid_text_growth_event.added_text, data["added_text"])
        self.assertEqual(
            rapid_text_growth_event.last_message_before_event, self.message
        )

    def test_log_rapid_text_growth_event_without_messages(self):
        """Test logging a rapid text growth event in a conversation without messages."""
        # Create a new conversation without messages
        new_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_events", args=[new_conversation.id])
        data = {
            "added_text": "First rapid text growth in conversation",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)

        # Verify rapid text growth event was created with no linked message
        rapid_text_growth_event = RapidTextGrowthEvent.objects.get(
            last_message_before_event__isnull=True
        )
        self.assertIsNone(rapid_text_growth_event.last_message_before_event)

    def test_log_rapid_text_growth_event_unauthorized(self):
        """Test logging a rapid text growth event in someone else's conversation."""
        self.client.login(username="teacheruser", password="password123")

        url = reverse("conversations:api_log_events", args=[self.conversation.id])
        data = {
            "added_text": "Unauthorized rapid text growth",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)

    def test_log_rapid_text_growth_event_not_logged_in(self):
        """Test logging a rapid text growth event without being logged in."""
        url = reverse("conversations:api_log_events", args=[self.conversation.id])
        data = {
            "added_text": "Unauthenticated rapid text growth",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        # Should redirect to login or return 302
        self.assertIn(response.status_code, [302, 403])

    def test_log_rapid_text_growth_event_invalid_json(self):
        """Test logging a rapid text growth event with invalid JSON."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_events", args=[self.conversation.id])

        response = self.client.post(
            url, "invalid json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_log_rapid_text_growth_event_conversation_not_found(self):
        """Test logging a rapid text growth event for a non-existent conversation."""
        self.client.login(username="studentuser", password="password123")

        # Use a random UUID that doesn't exist
        fake_uuid = "12345678-1234-1234-1234-123456789012"
        url = reverse("conversations:api_log_events", args=[fake_uuid])
        data = {
            "added_text": "Rapid text growth in non-existent conversation",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(
            url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)

    def test_multiple_rapid_text_growth_events(self):
        """Test logging multiple rapid text growth events in the same conversation."""
        self.client.login(username="studentuser", password="password123")

        url = reverse("conversations:api_log_events", args=[self.conversation.id])

        # Log first rapid text growth event
        data1 = {
            "added_text": "First rapid text growth content",
            "timestamp": timezone.now().isoformat(),
        }
        response1 = self.client.post(
            url, json.dumps(data1), content_type="application/json"
        )
        self.assertEqual(response1.status_code, 201)

        # Log second rapid text growth event
        data2 = {
            "added_text": "Second rapid text growth content with more text",
            "timestamp": timezone.now().isoformat(),
        }
        response2 = self.client.post(
            url, json.dumps(data2), content_type="application/json"
        )
        self.assertEqual(response2.status_code, 201)

        # Verify both events were created
        rapid_text_growth_events = RapidTextGrowthEvent.objects.filter(
            last_message_before_event__conversation=self.conversation
        )
        self.assertEqual(rapid_text_growth_events.count(), 2)
