"""
Tests for ensuring deleted conversations don't appear in homework list view.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Student, Teacher
from homeworks.models import Homework, Section
from conversations.models import Conversation, Submission
from homeworks.views import HomeworkListView
from homeworks.services import HomeworkService, SectionStatus
from courses.models import Course, CourseEnrollment, CourseTeacher

User = get_user_model()


class DeletedConversationsListViewTests(TestCase):
    """Test cases to ensure deleted conversations don't appear in homework list view."""

    def setUp(self):
        """Set up test data."""
        # Create test users
        self.student_user = User.objects.create_user(
            username="student1", email="student1@example.com", password="testpass123"
        )
        self.student_profile = Student.objects.create(user=self.student_user)

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher1@example.com", password="testpass123"
        )
        self.teacher_profile = Teacher.objects.create(user=self.teacher_user)

        # Create a course and enroll the student
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )

        # Add teacher to course
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher_profile, role="owner"
        )

        # Enroll student in course
        CourseEnrollment.objects.create(
            course=self.course, student=self.student_profile, is_active=True
        )

        # Create test homework with course (direct FK relationship)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            due_date=timezone.now()
            + timedelta(days=365),  # Future date to avoid overdue status
            created_by=self.teacher_profile,
            course=self.course,
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

    def test_deleted_conversation_not_shown_in_list_view(self):
        """
        Test that after deleting a conversation and creating a new one,
        only the new conversation appears in the homework list view.
        """
        # Step 1: Create initial conversation
        initial_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Get homework list view data
        view = HomeworkListView()
        initial_data = view._get_view_data(self.student_user)

        # Verify initial conversation appears in progress data
        homework_progress = None
        for homework in initial_data.homeworks:
            if homework.id == self.homework.id:
                homework_progress = homework
                break

        self.assertIsNotNone(homework_progress, "Homework should be found in list")
        self.assertIsNotNone(homework_progress.sections, "Section data should exist")

        # Find the section progress
        section_progress = None
        for section in homework_progress.sections:
            if section.id == self.section.id:
                section_progress = section
                break

        self.assertIsNotNone(section_progress, "Section progress should exist")
        self.assertEqual(
            section_progress.conversation_id,
            initial_conversation.id,
            "Initial conversation should appear in progress data",
        )

        # Step 2: Soft delete the conversation and create a new one
        initial_conversation.soft_delete()

        # Verify the conversation was actually soft deleted
        initial_conversation.refresh_from_db()
        self.assertTrue(
            initial_conversation.is_deleted,
            "Initial conversation should be soft deleted",
        )

        new_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Step 3: Get homework list view data again
        final_data = view._get_view_data(self.student_user)

        # Verify new conversation appears and old one doesn't
        homework_progress = None
        for homework in final_data.homeworks:
            if homework.id == self.homework.id:
                homework_progress = homework
                break

        self.assertIsNotNone(
            homework_progress, "Homework should still be found in list"
        )
        self.assertIsNotNone(
            homework_progress.sections, "Section data should still exist"
        )

        # Find the section progress
        section_progress = None
        for section in homework_progress.sections:
            if section.id == self.section.id:
                section_progress = section
                break

        self.assertIsNotNone(section_progress, "Section progress should still exist")

        # This is the key assertion - it should show the NEW conversation, not the deleted one
        self.assertEqual(
            section_progress.conversation_id,
            new_conversation.id,
            "New conversation should appear in progress data, not the deleted one",
        )

        # Additional verification: ensure the deleted conversation ID is NOT in the progress
        self.assertNotEqual(
            section_progress.conversation_id,
            initial_conversation.id,
            "Deleted conversation should NOT appear in progress data",
        )

    def test_deleted_conversation_with_submission_bug(self):
        """
        Test the specific bug scenario where submissions from deleted conversations
        still affect the homework progress display:
        1. Student creates conversation and submits it
        2. Student deletes conversation and starts new one
        3. Progress should show new conversation, not submitted status
        """
        # Create homework with course (direct FK relationship)
        homework = Homework.objects.create(
            title="Test Homework with Submission",
            description="Test homework description",
            due_date=timezone.now() + timedelta(days=7),
            created_by=self.teacher_profile,
            course=self.course,
        )

        section = Section.objects.create(
            homework=homework,
            title="Test Section with Submission",
            content="Test section content",
            order=1,
        )

        # Step 1: Create initial conversation and submit it
        initial_conversation = Conversation.objects.create(
            user=self.student_user, section=section
        )

        # Create submission for the initial conversation
        _submission = Submission.objects.create(conversation=initial_conversation)

        # Verify initial state - should show as submitted
        progress = HomeworkService.get_student_homework_progress(
            self.student_profile, homework
        )
        section_progress = progress.sections_progress[0]

        self.assertEqual(section_progress.status, SectionStatus.SUBMITTED)
        self.assertEqual(section_progress.conversation_id, initial_conversation.id)

        # Step 2: Delete the conversation (soft delete)
        initial_conversation.soft_delete()
        initial_conversation.refresh_from_db()
        self.assertTrue(initial_conversation.is_deleted)

        # Step 3: Create new conversation
        new_conversation = Conversation.objects.create(
            user=self.student_user, section=section
        )

        # Step 4: Check progress - this is where the bug was occurring
        # The progress should show the new conversation as IN_PROGRESS
        # Before the fix, it would still show as SUBMITTED because
        # the submission query didn't filter out deleted conversations
        progress = HomeworkService.get_student_homework_progress(
            self.student_profile, homework
        )
        section_progress = progress.sections_progress[0]

        # This assertion verifies the bug is fixed
        self.assertEqual(
            section_progress.status,
            SectionStatus.IN_PROGRESS,
            "Should show IN_PROGRESS for new conversation, not SUBMITTED from deleted one",
        )
        self.assertEqual(
            section_progress.conversation_id,
            new_conversation.id,
            "Should show new conversation ID, not old one",
        )

        # Additional verification: ensure the submission still exists but is from deleted conversation
        self.assertTrue(
            Submission.objects.filter(conversation=initial_conversation).exists()
        )
        self.assertTrue(initial_conversation.is_deleted)
