"""
Tests for the HomeworkListView progress calculation logic.

This module tests the view-level percentage calculations that were moved
from the service layer to simplify the codebase.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from homeworks.models import Homework, Section
from homeworks.views import HomeworkListView
from homeworks.services import HomeworkService, HomeworkCreateData, SectionCreateData
from accounts.models import Teacher, Student
from conversations.models import Conversation

User = get_user_model()


class TestHomeworkListViewProgress(TestCase):
    """Test cases for HomeworkListView progress calculation logic."""

    def setUp(self):
        """Set up test data."""
        # Create a test teacher
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create a test student
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create test homework with 4 sections
        homework_data = HomeworkCreateData(
            title="Test Homework",
            description="Test Description",
            due_date=timezone.now() + timedelta(days=7),
            sections=[
                SectionCreateData(title="Section 1", content="Content 1", order=1),
                SectionCreateData(title="Section 2", content="Content 2", order=2),
                SectionCreateData(title="Section 3", content="Content 3", order=3),
                SectionCreateData(title="Section 4", content="Content 4", order=4),
            ],
        )

        result = HomeworkService.create_homework_with_sections(
            homework_data, self.teacher
        )
        self.homework = Homework.objects.get(id=result.homework_id)
        self.sections = list(
            Section.objects.filter(homework=self.homework).order_by("order")
        )

    def test_progress_percentages_no_activity(self):
        """Test percentage calculations when student has no activity."""
        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        # Should have one homework
        self.assertEqual(len(data.homeworks), 1)
        homework_item = data.homeworks[0]

        # No progress should mean 0% for both
        self.assertEqual(homework_item.completed_percentage, 0)
        self.assertEqual(homework_item.in_progress_percentage, 0)

    def test_progress_percentages_partial_in_progress(self):
        """Test percentage calculations with some sections in progress."""
        # Create conversations for 2 out of 4 sections (50% in progress)
        Conversation.objects.create(user=self.student_user, section=self.sections[0])
        Conversation.objects.create(user=self.student_user, section=self.sections[1])

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        homework_item = data.homeworks[0]

        # 2 out of 4 sections in progress = 50%
        self.assertEqual(homework_item.completed_percentage, 0)
        self.assertEqual(homework_item.in_progress_percentage, 50)

    def test_progress_percentages_partial_completed(self):
        """Test percentage calculations with some sections completed."""
        from conversations.models import Submission

        # Create conversations and submissions for 1 out of 4 sections (25% completed)
        conv1 = Conversation.objects.create(
            user=self.student_user, section=self.sections[0]
        )
        Submission.objects.create(conversation=conv1)

        # Create conversation without submission for another section (25% in progress)
        Conversation.objects.create(user=self.student_user, section=self.sections[1])

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        homework_item = data.homeworks[0]

        # 1 out of 4 sections completed = 25%, 1 out of 4 in progress = 25%
        self.assertEqual(homework_item.completed_percentage, 25)
        self.assertEqual(homework_item.in_progress_percentage, 25)

    def test_progress_percentages_all_completed(self):
        """Test percentage calculations when all sections are completed."""
        from conversations.models import Submission

        # Create conversations and submissions for all sections
        for section in self.sections:
            conv = Conversation.objects.create(user=self.student_user, section=section)
            Submission.objects.create(conversation=conv)

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        homework_item = data.homeworks[0]

        # All sections completed = 100%
        self.assertEqual(homework_item.completed_percentage, 100)
        self.assertEqual(homework_item.in_progress_percentage, 0)

    def test_progress_percentages_overdue_scenarios(self):
        """Test percentage calculations for overdue homework."""
        # Make homework overdue
        self.homework.due_date = timezone.now() - timedelta(days=1)
        self.homework.save()

        # Create conversation for one section (should be in_progress_overdue)
        Conversation.objects.create(user=self.student_user, section=self.sections[0])

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        homework_item = data.homeworks[0]

        # 1 out of 4 sections in progress (overdue) = 25%
        self.assertEqual(homework_item.completed_percentage, 0)
        self.assertEqual(homework_item.in_progress_percentage, 25)

    def test_progress_percentages_rounding(self):
        """Test percentage calculations with rounding (3 sections for 33.33% scenarios)."""
        # Create homework with 3 sections for testing rounding
        homework_data = HomeworkCreateData(
            title="Rounding Test Homework",
            description="Test Description",
            due_date=timezone.now() + timedelta(days=7),
            sections=[
                SectionCreateData(title="Section A", content="Content A", order=1),
                SectionCreateData(title="Section B", content="Content B", order=2),
                SectionCreateData(title="Section C", content="Content C", order=3),
            ],
        )

        result = HomeworkService.create_homework_with_sections(
            homework_data, self.teacher
        )
        homework_3_sections = Homework.objects.get(id=result.homework_id)
        sections_3 = list(
            Section.objects.filter(homework=homework_3_sections).order_by("order")
        )

        # Create conversation for 1 out of 3 sections (33.33% -> should round to 33%)
        Conversation.objects.create(user=self.student_user, section=sections_3[0])

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        # Find the 3-section homework
        homework_item = None
        for item in data.homeworks:
            if item.title == "Rounding Test Homework":
                homework_item = item
                break

        self.assertIsNotNone(homework_item)

        # 1 out of 3 sections = 33.33% -> rounds to 33%
        self.assertEqual(homework_item.completed_percentage, 0)
        self.assertEqual(homework_item.in_progress_percentage, 33)

    def test_progress_percentages_teacher_view(self):
        """Test that teacher view doesn't calculate percentages."""
        view = HomeworkListView()
        data = view._get_view_data(self.teacher_user)

        # Should have one homework
        self.assertEqual(len(data.homeworks), 1)
        homework_item = data.homeworks[0]

        # Teacher view should have default 0% values and no progress data
        self.assertEqual(homework_item.completed_percentage, 0)
        self.assertEqual(homework_item.in_progress_percentage, 0)
        self.assertIsNone(homework_item.sections)
