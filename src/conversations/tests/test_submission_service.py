"""
Tests for the SubmissionService class.

This module contains tests for the SubmissionService following
the testing-first architecture approach.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from conversations.models import Conversation, Submission
from conversations.services import SubmissionService
from homeworks.models import Homework, Section
from courses.models import Course
from accounts.models import Teacher, Student

User = get_user_model()


class SubmissionServiceTestCase(TestCase):
    """Base test case for SubmissionService with common setup."""

    def setUp(self):
        """Set up test data."""
        # Create a teacher user
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create course for homework assignment
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create a student user
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a homework with a section
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            due_date=timezone.now() + timedelta(days=7),
            created_by=self.teacher,
            course=self.course,
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test Content",
            order=1,
        )

        # Create a conversation
        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )


class TestSubmissionService(SubmissionServiceTestCase):
    """Test cases for SubmissionService methods."""

    def test_submit_section_new_submission(self):
        """Test submitting a section for the first time."""
        # Submit the section
        result = SubmissionService.submit_section(self.student_user, self.conversation)

        # Check result
        self.assertIsInstance(result, SubmissionService.SubmissionResult)
        self.assertTrue(result.success)
        self.assertTrue(result.is_new)
        self.assertIsNotNone(result.submission_id)
        self.assertEqual(result.conversation_id, self.conversation.id)
        self.assertEqual(result.section_id, self.section.id)

        # Check submission was created
        submission = Submission.objects.get(id=result.submission_id)
        self.assertEqual(submission.conversation, self.conversation)

    def test_submit_section_existing_submission(self):
        """Test submitting a section when a submission already exists."""
        # Create an initial submission
        existing_submission = Submission.objects.create(conversation=self.conversation)

        # Create a new conversation for the same section
        new_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Submit with the new conversation
        result = SubmissionService.submit_section(self.student_user, new_conversation)

        # Check result
        self.assertTrue(result.success)
        self.assertFalse(result.is_new)  # Should indicate this is an update

        # Check that the existing submission was updated
        updated_submission = Submission.objects.get(id=result.submission_id)
        self.assertEqual(updated_submission.id, existing_submission.id)
        self.assertEqual(updated_submission.conversation, new_conversation)

    def test_get_submission_data(self):
        """Test retrieving submission data."""
        # Create a submission
        submission = Submission.objects.create(conversation=self.conversation)

        # Get submission data
        data = SubmissionService.get_submission_data(submission.id)

        # Check result
        self.assertIsNotNone(data)
        self.assertEqual(data.id, submission.id)
        self.assertEqual(data.conversation_id, self.conversation.id)
        self.assertEqual(data.section_id, self.section.id)
        self.assertEqual(data.section_title, self.section.title)
        self.assertEqual(data.student_id, self.student.id)
        self.assertIn(self.student_user.username, data.student_name)

    def test_get_student_submissions(self):
        """Test retrieving all submissions for a student."""
        # Create two submissions for different sections
        submission1 = Submission.objects.create(conversation=self.conversation)

        # Create another section and conversation
        section2 = Section.objects.create(
            homework=self.homework,
            title="Another Section",
            content="More content",
            order=2,
        )

        conversation2 = Conversation.objects.create(
            user=self.student_user, section=section2
        )

        submission2 = Submission.objects.create(conversation=conversation2)

        # Get student submissions
        submissions = SubmissionService.get_student_submissions(self.student)

        # Check result
        self.assertEqual(len(submissions), 2)
        self.assertEqual({s.id for s in submissions}, {submission1.id, submission2.id})

    @patch("homeworks.models.Section.objects.filter")
    def test_auto_submit_overdue_sections(self, mock_sections_filter):
        """Test auto-submitting overdue sections."""
        # Mock overdue sections
        mock_sections_filter.return_value.select_related.return_value = [self.section]

        # Run auto-submit
        result = SubmissionService.auto_submit_overdue_sections()

        # Check result
        self.assertIsInstance(result, SubmissionService.AutoSubmitResult)
        self.assertGreaterEqual(result.total_sections, 0)
        self.assertGreaterEqual(result.processed_sections, 0)
        self.assertGreaterEqual(result.created_submissions, 0)
        self.assertGreaterEqual(result.error_count, 0)
        self.assertIsInstance(result.details, list)
