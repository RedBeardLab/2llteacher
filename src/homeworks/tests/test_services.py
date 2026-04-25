"""
Tests for the HomeworkService class.

This module contains comprehensive tests for the HomeworkService following
the testing-first architecture approach.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import uuid

from homeworks.models import Homework, Section
from homeworks.services import (
    HomeworkService,
    HomeworkCreateData,
    SectionCreateData,
    HomeworkCreateResult,
    HomeworkProgressData,
    HomeworkDetailData,
    HomeworkUpdateData,
    SectionStatus,
)
from accounts.models import Teacher, Student
from courses.models import Course

User = get_user_model()


class HomeworkServiceTestCase(TestCase):
    """Base test case for HomeworkService with common setup."""

    def setUp(self):
        """Set up test data."""
        # Create a test user and teacher
        self.user = User.objects.create_user(
            username="testteacher", email="test@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.user)

        # Create student user
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create course for homework assignment
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create test data for sections
        self.section1 = SectionCreateData(
            title="Section 1",
            content="Test content for section 1",
            order=1,
            solution="Test solution for section 1",
        )

        self.section2 = SectionCreateData(
            title="Section 2",
            content="Test content for section 2",
            order=2,
            solution="Test solution for section 2",
        )

        # Create test data for homework
        self.homework_data = HomeworkCreateData(
            title="Test Homework",
            description="Test Description for homework",
            due_date=timezone.now() + timedelta(days=7),
            course_id=self.course.id,
            sections=[self.section1, self.section2],
            llm_config=None,
        )


class TestHomeworkServiceCreate(HomeworkServiceTestCase):
    """Test cases for HomeworkService.create_homework_with_sections method."""

    def test_create_homework_success(self):
        """Test creating a homework with sections successfully."""
        result = HomeworkService.create_homework_with_sections(
            self.homework_data, self.teacher
        )

        # Check result is of correct type and successful
        self.assertIsInstance(result, HomeworkCreateResult)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.homework_id)
        self.assertEqual(len(result.section_ids), 2)

        # Check homework was created with correct data
        homework = Homework.objects.get(id=result.homework_id)
        self.assertEqual(homework.title, self.homework_data.title)
        self.assertEqual(homework.description, self.homework_data.description)
        self.assertEqual(homework.created_by, self.teacher)

        # Check sections were created with correct data
        sections = Section.objects.filter(homework=homework).order_by("order")
        self.assertEqual(sections.count(), 2)
        self.assertEqual(sections[0].title, self.section1.title)
        self.assertEqual(sections[0].content, self.section1.content)
        self.assertEqual(sections[0].order, self.section1.order)
        self.assertEqual(sections[1].title, self.section2.title)
        self.assertEqual(sections[1].content, self.section2.content)
        self.assertEqual(sections[1].order, self.section2.order)

        # Check solutions were created
        self.assertIsNotNone(sections[0].solution)
        self.assertEqual(sections[0].solution.content, self.section1.solution)
        self.assertIsNotNone(sections[1].solution)
        self.assertEqual(sections[1].solution.content, self.section2.solution)

    def test_create_homework_without_solutions(self):
        """Test creating a homework with sections that don't have solutions."""
        section1 = SectionCreateData(
            title="Section 1 No Solution", content="Content 1", order=1
        )

        section2 = SectionCreateData(
            title="Section 2 No Solution", content="Content 2", order=2
        )

        homework_data = HomeworkCreateData(
            title="Homework Without Solutions",
            description="Test Description",
            due_date=timezone.now() + timedelta(days=7),
            course_id=self.course.id,
            sections=[section1, section2],
        )

        result = HomeworkService.create_homework_with_sections(
            homework_data, self.teacher
        )

        # Check result
        self.assertTrue(result.success)

        # Check sections were created without solutions
        homework = Homework.objects.get(id=result.homework_id)
        sections = Section.objects.filter(homework=homework).order_by("order")

        self.assertIsNone(sections[0].solution)
        self.assertIsNone(sections[1].solution)

    def test_create_homework_with_validation_error(self):
        """Test handling validation errors when creating a homework."""
        # Create invalid data (missing title)
        invalid_data = HomeworkCreateData(
            title="",
            description="Test",
            due_date=timezone.now() + timedelta(days=7),
            course_id=self.course.id,
            sections=[self.section1],
        )

        result = HomeworkService.create_homework_with_sections(
            invalid_data, self.teacher
        )

        # Check result indicates failure
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class TestHomeworkServiceProgress(HomeworkServiceTestCase):
    """Test cases for HomeworkService.get_student_homework_progress method."""

    def setUp(self):
        """Set up test data with a homework and some submission data."""
        super().setUp()

        # Create a real homework with sections
        result = HomeworkService.create_homework_with_sections(
            self.homework_data, self.teacher
        )
        self.homework = Homework.objects.get(id=result.homework_id)
        self.sections = list(
            Section.objects.filter(homework=self.homework).order_by("order")
        )

        # We'll need to simulate submissions in individual tests

    def test_get_progress_no_submissions(self):
        """Test getting progress when student has no submissions."""
        progress_data = HomeworkService.get_student_homework_progress(
            self.student, self.homework
        )

        # Check result is correct type
        self.assertIsInstance(progress_data, HomeworkProgressData)
        self.assertEqual(progress_data.homework_id, self.homework.id)

        # Check there are 2 sections in progress data
        self.assertEqual(len(progress_data.sections_progress), 2)

        # All sections should be marked as not started
        for section_progress in progress_data.sections_progress:
            self.assertEqual(section_progress.status, SectionStatus.NOT_STARTED)
            self.assertIsNone(section_progress.conversation_id)

    @patch("conversations.models.Submission.objects.filter")
    def test_get_progress_with_submissions(self, mock_submission_filter):
        """Test getting progress when student has submissions."""
        # Setup mock for submission query
        mock_submission = MagicMock()
        mock_submission.conversation.id = uuid.uuid4()
        mock_submission_filter.return_value.first.return_value = mock_submission

        progress_data = HomeworkService.get_student_homework_progress(
            self.student, self.homework
        )

        # Should be called once per section
        self.assertEqual(mock_submission_filter.call_count, 2)

        # Check status and conversation ID for each section
        for section_progress in progress_data.sections_progress:
            self.assertEqual(section_progress.status, SectionStatus.SUBMITTED)
            self.assertIsNotNone(section_progress.conversation_id)

    def test_get_progress_with_active_conversations(self):
        """Test getting progress when student has active conversations (the fix)."""
        from conversations.models import Conversation

        # Create a conversation for the first section (student started working)
        conversation = Conversation.objects.create(
            user=self.student_user, section=self.sections[0]
        )

        progress_data = HomeworkService.get_student_homework_progress(
            self.student, self.homework
        )

        # Check progress data - should have 2 sections, none completed yet
        self.assertEqual(len(progress_data.sections_progress), 2)

        # First section should be in progress
        section1_progress = progress_data.sections_progress[0]
        self.assertEqual(section1_progress.status, SectionStatus.IN_PROGRESS)
        self.assertEqual(section1_progress.conversation_id, conversation.id)

        # Second section should still be not started
        section2_progress = progress_data.sections_progress[1]
        self.assertEqual(section2_progress.status, SectionStatus.NOT_STARTED)
        self.assertIsNone(section2_progress.conversation_id)

    def test_get_progress_overdue_with_conversations(self):
        """Test progress tracking for overdue homework with active conversations."""
        from conversations.models import Conversation

        # Make homework overdue
        self.homework.due_date = timezone.now() - timedelta(days=1)
        self.homework.save()

        # Create conversation for first section
        conversation = Conversation.objects.create(
            user=self.student_user, section=self.sections[0]
        )

        progress_data = HomeworkService.get_student_homework_progress(
            self.student, self.homework
        )

        # First section should be in_progress_overdue (started but overdue)
        section1_progress = progress_data.sections_progress[0]
        self.assertEqual(section1_progress.status, SectionStatus.IN_PROGRESS_OVERDUE)
        self.assertEqual(section1_progress.conversation_id, conversation.id)

        # Second section should be overdue (never started and overdue)
        section2_progress = progress_data.sections_progress[1]
        self.assertEqual(section2_progress.status, SectionStatus.OVERDUE)
        self.assertIsNone(section2_progress.conversation_id)

    def test_get_progress_deleted_conversations_ignored(self):
        """Test that soft-deleted conversations are ignored in progress tracking."""
        from conversations.models import Conversation

        # Create a conversation and then soft delete it
        conversation = Conversation.objects.create(
            user=self.student_user, section=self.sections[0]
        )
        conversation.soft_delete()

        progress_data = HomeworkService.get_student_homework_progress(
            self.student, self.homework
        )

        # Should not detect the deleted conversation
        section1_progress = progress_data.sections_progress[0]
        self.assertEqual(section1_progress.status, SectionStatus.NOT_STARTED)
        self.assertIsNone(section1_progress.conversation_id)


class TestHomeworkServiceDetails(HomeworkServiceTestCase):
    """Test cases for HomeworkService.get_homework_with_sections method."""

    def setUp(self):
        """Set up test data with a homework."""
        super().setUp()

        # Create a real homework with sections
        result = HomeworkService.create_homework_with_sections(
            self.homework_data, self.teacher
        )
        self.homework_id = result.homework_id

    def test_get_homework_details_success(self):
        """Test getting detailed homework data successfully."""
        detail_data = HomeworkService.get_homework_with_sections(self.homework_id)

        # Check result is correct type
        self.assertIsInstance(detail_data, HomeworkDetailData)
        assert detail_data is not None
        self.assertEqual(detail_data.id, self.homework_id)
        self.assertEqual(detail_data.title, self.homework_data.title)
        self.assertEqual(detail_data.description, self.homework_data.description)

        # Check sections data
        self.assertEqual(len(detail_data.sections), 2)
        assert detail_data.sections is not None
        self.assertEqual(detail_data.sections[0].title, self.section1.title)
        self.assertEqual(detail_data.sections[1].title, self.section2.title)

    def test_get_homework_not_found(self):
        """Test getting homework that doesn't exist."""
        non_existent_id = uuid.uuid4()
        result = HomeworkService.get_homework_with_sections(non_existent_id)

        # Should return None for non-existent homework
        self.assertIsNone(result)


class TestHomeworkServiceUpdate(HomeworkServiceTestCase):
    """Test cases for HomeworkService.update_homework method."""

    def setUp(self):
        """Set up test data with a homework to update."""
        super().setUp()

        # Create a real homework with sections
        result = HomeworkService.create_homework_with_sections(
            self.homework_data, self.teacher
        )
        self.homework_id = result.homework_id
        self.homework = Homework.objects.get(id=self.homework_id)
        self.sections = list(
            Section.objects.filter(homework=self.homework).order_by("order")
        )

    def test_update_homework_basic_fields(self):
        """Test updating basic homework fields."""
        update_data = HomeworkUpdateData(
            title="Updated Title",
            description="Updated Description",
            due_date=timezone.now() + timedelta(days=14),
        )

        result = HomeworkService.update_homework(self.homework_id, update_data)

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.homework_id, self.homework_id)

        # Check homework was updated
        updated_homework = Homework.objects.get(id=self.homework_id)
        self.assertEqual(updated_homework.title, update_data.title)
        self.assertEqual(updated_homework.description, update_data.description)

    def test_update_homework_add_section(self):
        """Test adding a new section to an existing homework."""
        new_section = SectionCreateData(
            title="New Section", content="New Content", order=3, solution="New Solution"
        )

        update_data = HomeworkUpdateData(sections_to_create=[new_section])

        result = HomeworkService.update_homework(self.homework_id, update_data)

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(len(result.created_section_ids), 1)

        # Check section was added
        sections = Section.objects.filter(homework_id=self.homework_id).order_by(
            "order"
        )
        self.assertEqual(sections.count(), 3)
        self.assertEqual(sections[2].title, new_section.title)
        self.assertEqual(sections[2].content, new_section.content)
        self.assertEqual(sections[2].order, new_section.order)

    def test_update_homework_swaps_section_order(self):
        """Test reordering existing sections without transient uniqueness errors."""
        update_data = HomeworkUpdateData(
            sections_to_update=[
                {
                    "id": self.sections[0].id,
                    "title": self.sections[0].title,
                    "content": self.sections[0].content,
                    "order": 2,
                    "solution": self.sections[0].solution.content,
                    "section_type": self.sections[0].section_type,
                },
                {
                    "id": self.sections[1].id,
                    "title": self.sections[1].title,
                    "content": self.sections[1].content,
                    "order": 1,
                    "solution": self.sections[1].solution.content,
                    "section_type": self.sections[1].section_type,
                },
            ]
        )

        result = HomeworkService.update_homework(self.homework_id, update_data)

        self.assertTrue(result.success, result.error)
        sections = list(
            Section.objects.filter(homework_id=self.homework_id).order_by("order")
        )
        self.assertEqual(
            [section.id for section in sections],
            [self.sections[1].id, self.sections[0].id],
        )
        self.assertEqual([section.order for section in sections], [1, 2])

    def test_update_homework_delete_section(self):
        """Test deleting a section from an existing homework."""
        update_data = HomeworkUpdateData(sections_to_delete=[self.sections[0].id])

        result = HomeworkService.update_homework(self.homework_id, update_data)

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(len(result.deleted_section_ids), 1)

        # Check section was deleted
        sections = Section.objects.filter(homework_id=self.homework_id)
        self.assertEqual(sections.count(), 1)
        self.assertEqual(sections[0].id, self.sections[1].id)

    def test_update_nonexistent_homework(self):
        """Test updating a homework that doesn't exist."""
        non_existent_id = uuid.uuid4()
        update_data = HomeworkUpdateData(title="New Title")

        result = HomeworkService.update_homework(non_existent_id, update_data)

        # Should indicate failure
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class TestHomeworkServiceDelete(HomeworkServiceTestCase):
    """Test cases for HomeworkService.delete_homework method."""

    def setUp(self):
        """Set up test data with a homework to delete."""
        super().setUp()

        # Create a real homework with sections
        result = HomeworkService.create_homework_with_sections(
            self.homework_data, self.teacher
        )
        self.homework_id = result.homework_id

    def test_delete_homework_success(self):
        """Test deleting a homework successfully."""
        # First verify it exists
        self.assertTrue(Homework.objects.filter(id=self.homework_id).exists())

        # Delete it
        result = HomeworkService.delete_homework(self.homework_id)

        # Check result
        self.assertTrue(result)

        # Verify it's gone
        self.assertFalse(Homework.objects.filter(id=self.homework_id).exists())

        # Verify sections are also deleted (cascade)
        self.assertEqual(
            Section.objects.filter(homework_id=self.homework_id).count(), 0
        )

    def test_delete_nonexistent_homework(self):
        """Test deleting a homework that doesn't exist."""
        non_existent_id = uuid.uuid4()
        result = HomeworkService.delete_homework(non_existent_id)

        # Should return False
        self.assertFalse(result)
