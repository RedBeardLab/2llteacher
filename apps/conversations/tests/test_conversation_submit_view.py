"""
Tests for the ConversationSubmitView.

This module tests the functionality for directly submitting conversations.
"""

from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from uuid import UUID
from datetime import timedelta
from django.utils import timezone

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section
from conversations.models import Conversation, Message, Submission


class ConversationSubmitViewTests(TestCase):
    """Test cases for the ConversationSubmitView."""

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

        # Create another student for permission testing
        self.other_student_user = User.objects.create_user(
            username="otherstudent",
            email="otherstudent@example.com",
            first_name="Other",
            last_name="Student",
            password="password123",
        )
        self.other_student = Student.objects.create(user=self.other_student_user)

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

        # Create a conversation for the student
        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Add messages to the conversation
        Message.objects.create(
            conversation=self.conversation,
            content="Initial AI message",
            message_type="ai",
        )

        Message.objects.create(
            conversation=self.conversation,
            content="Student response",
            message_type="student",
        )

        # URL for submitting the conversation
        self.submit_url = reverse(
            "conversations:submit_conversation",
            kwargs={"conversation_id": self.conversation.id},
        )

    def test_submit_view_requires_login(self):
        """Test that submitting a conversation requires login."""
        response = self.client.post(self.submit_url)

        # Check that the user is redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))

    def test_submit_view_requires_student_role(self):
        """Test that only students can submit conversations."""
        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Attempt to submit the conversation
        response = self.client.post(self.submit_url)

        # Check that access is forbidden for teachers
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_submit_other_student_conversation(self):
        """Test that a student cannot submit another student's conversation."""
        # Login as the other student
        self.client.login(username="otherstudent", password="password123")

        # Attempt to submit the first student's conversation
        response = self.client.post(self.submit_url)

        # Check that access is forbidden
        self.assertEqual(response.status_code, 403)

    def test_get_request_not_allowed(self):
        """Test that GET requests are not allowed for this view."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Try GET request
        response = self.client.get(self.submit_url)

        # Check that GET is not allowed (should be 405 Method Not Allowed)
        self.assertEqual(response.status_code, 405)

    @patch("conversations.services.SubmissionService.submit_section")
    def test_student_can_submit_own_conversation(self, mock_submit_section):
        """Test that a student can submit their own conversation."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock the service response
        mock_result = MagicMock(
            success=True,
            submission_id=UUID("12345678-1234-5678-1234-567812345678"),
            conversation_id=self.conversation.id,
            section_id=self.section.id,
            is_new=True,
        )
        mock_submit_section.return_value = mock_result

        # Submit the conversation
        response = self.client.post(self.submit_url)

        # Check that the service was called correctly
        mock_submit_section.assert_called_once()
        args = mock_submit_section.call_args[0]
        self.assertEqual(args[0], self.student_user)
        self.assertEqual(args[1].id, self.conversation.id)

        # Check redirect to section detail
        self.assertEqual(response.status_code, 302)
        expected_url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework.id, "section_id": self.section.id},
        )
        self.assertEqual(response["Location"], expected_url)

    @patch("conversations.services.SubmissionService.submit_section")
    def test_submission_service_error(self, mock_submit_section):
        """Test error handling when submission service fails."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Mock service error response
        mock_result = MagicMock(success=False, error="Failed to submit conversation")
        mock_submit_section.return_value = mock_result

        # Attempt to submit the conversation
        response = self.client.post(self.submit_url)

        # Check that we're redirected back to conversation detail
        self.assertEqual(response.status_code, 302)
        expected_url = reverse(
            "conversations:detail", kwargs={"conversation_id": self.conversation.id}
        )
        self.assertEqual(response["Location"], expected_url)

    def test_conversation_does_not_exist(self):
        """Test the view behavior when the conversation does not exist."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Create URL with non-existent conversation ID
        non_existent_url = reverse(
            "conversations:submit_conversation",
            kwargs={"conversation_id": UUID("00000000-0000-0000-0000-000000000000")},
        )

        # Try to submit the non-existent conversation
        response = self.client.post(non_existent_url)

        # Check response is a 404
        self.assertEqual(response.status_code, 404)

    def test_cannot_submit_deleted_conversation(self):
        """Test that a deleted conversation cannot be submitted."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Soft delete the conversation
        self.conversation.soft_delete()

        # Attempt to submit the deleted conversation
        response = self.client.post(self.submit_url)

        # Check that we're redirected back to conversation detail with error
        self.assertEqual(response.status_code, 302)
        expected_url = reverse(
            "conversations:detail", kwargs={"conversation_id": self.conversation.id}
        )
        self.assertEqual(response["Location"], expected_url)

    @patch("conversations.services.SubmissionService.submit_section")
    def test_update_existing_submission(self, mock_submit_section):
        """Test updating an existing submission."""
        # Login as student
        self.client.login(username="studentuser", password="password123")

        # Create an existing submission
        existing_submission = Submission.objects.create(conversation=self.conversation)

        # Mock service response for updating existing submission
        mock_result = MagicMock(
            success=True,
            submission_id=existing_submission.id,
            conversation_id=self.conversation.id,
            section_id=self.section.id,
            is_new=False,
        )
        mock_submit_section.return_value = mock_result

        # Submit the conversation
        response = self.client.post(self.submit_url)

        # Check that the service was called
        mock_submit_section.assert_called_once()

        # Check redirect to section detail
        self.assertEqual(response.status_code, 302)
        expected_url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework.id, "section_id": self.section.id},
        )
        self.assertEqual(response["Location"], expected_url)

    def test_teacher_conversation_cannot_be_submitted(self):
        """Test that teacher test conversations cannot be submitted."""
        # Create a teacher test conversation
        teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )

        # Login as teacher
        self.client.login(username="teacheruser", password="password123")

        # Try to submit the teacher conversation
        teacher_submit_url = reverse(
            "conversations:submit_conversation",
            kwargs={"conversation_id": teacher_conversation.id},
        )
        response = self.client.post(teacher_submit_url)

        # Check that access is forbidden
        self.assertEqual(response.status_code, 403)
