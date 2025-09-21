"""
Tests for the SectionDetailView.

This module tests the SectionDetailView, which displays a single section
with its conversations and submission information.
"""

import uuid
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section, SectionSolution
from conversations.models import Conversation, Submission


class SectionDetailViewTestCase(TestCase):
    """Test the SectionDetailView."""

    def setUp(self):
        """Set up test data."""
        # Create teacher user
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create student user
        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create homework with timezone-naive datetime
        import datetime

        # Use a naive datetime object for the test
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=datetime.datetime(2030, 1, 1),
        )

        # Create section without solution
        self.section_without_solution = Section.objects.create(
            homework=self.homework,
            title="Test Section No Solution",
            content="Test Content",
            order=1,
        )

        # Create section with solution
        solution = SectionSolution.objects.create(content="Test Solution")
        self.section_with_solution = Section.objects.create(
            homework=self.homework,
            title="Test Section With Solution",
            content="Test Content",
            order=2,
            solution=solution,
        )

        # Create conversation for student
        self.student_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section_with_solution
        )

        # Create submission for student
        self.student_submission = Submission.objects.create(
            conversation=self.student_conversation
        )

        # Create conversation for teacher
        self.teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section_with_solution
        )

        # Set up client
        self.client = Client()

    def test_section_detail_view_teacher_access(self):
        """Test teacher can access the section detail view."""
        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Access section without solution
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.section_without_solution.id,
            },
        )
        response = self.client.get(url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/section_detail.html")

        # Check context data
        self.assertEqual(response.context["data"].homework_id, self.homework.id)
        self.assertEqual(
            response.context["data"].section_id, self.section_without_solution.id
        )
        self.assertEqual(response.context["data"].is_teacher, True)
        self.assertEqual(response.context["data"].is_student, False)
        self.assertEqual(response.context["data"].has_solution, False)

        # Access section with solution
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.section_with_solution.id,
            },
        )
        response = self.client.get(url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/section_detail.html")

        # Check context data for section with solution
        self.assertEqual(response.context["data"].has_solution, True)
        self.assertEqual(response.context["data"].solution_content, "Test Solution")

    def test_section_detail_view_student_access(self):
        """Test student can access the section detail view."""
        # Login as student
        self.client.login(username="student", password="password")

        # Access section with conversation and submission
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.section_with_solution.id,
            },
        )
        response = self.client.get(url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/section_detail.html")

        # Check context data
        self.assertEqual(response.context["data"].is_teacher, False)
        self.assertEqual(response.context["data"].is_student, True)
        self.assertIsNotNone(response.context["data"].conversations)
        self.assertIsNotNone(response.context["data"].submission)
        self.assertEqual(
            response.context["data"].submission["id"], self.student_submission.id
        )

    def test_section_detail_view_no_access(self):
        """Test unauthenticated user cannot access the section detail view."""
        # Access section as unauthenticated user
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.section_with_solution.id,
            },
        )
        response = self.client.get(url)

        # Check user is redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_section_detail_view_invalid_section(self):
        """Test accessing non-existent section redirects to homework detail."""
        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Try to access non-existent section
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": uuid.uuid4(),  # Random UUID that doesn't exist
            },
        )
        response = self.client.get(url)

        # Check user is redirected to homework detail
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("homeworks:detail", kwargs={"homework_id": self.homework.id}),
        )

    def test_section_detail_conversations_and_submission(self):
        """Test section detail view handles conversations and submissions correctly."""
        # Login as student
        self.client.login(username="student", password="password")

        # Access section with existing conversation and submission
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.section_with_solution.id,
            },
        )
        response = self.client.get(url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)

        # Check for conversation and submission data in context
        self.assertIsNotNone(response.context["data"].conversations)
        self.assertIsNotNone(response.context["data"].submission)
