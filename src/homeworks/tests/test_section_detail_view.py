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
from conversations.models import Conversation, Submission, SectionAnswer
from courses.models import Course, CourseEnrollment, CourseTeacher


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

        # Create a course and enroll the student
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )

        # Add teacher to course
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )

        # Enroll student in course
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        # Create homework with timezone-naive datetime and course (direct FK relationship)
        import datetime

        # Use a naive datetime object for the test
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            course=self.course,
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
        self.assertIn("teacher", response.context["data"].user_roles)
        self.assertNotIn("student", response.context["data"].user_roles)
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
        self.assertNotIn("teacher", response.context["data"].user_roles)
        self.assertIn("student", response.context["data"].user_roles)
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


class SectionDetailViewNonInteractiveTestCase(TestCase):
    """Test SectionDetailView behaviour for non-interactive sections."""

    def setUp(self):
        import datetime

        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Course", code="C101", description="", is_active=True
        )
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.homework = Homework.objects.create(
            title="HW",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=datetime.datetime(2030, 1, 1),
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What is 2+2?",
            order=1,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

        self.url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework.id, "section_id": self.ni_section.id},
        )

    def test_student_sees_non_interactive_section_type(self):
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["data"].section_type, "non_interactive")

    def test_student_has_no_conversations_for_non_interactive(self):
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertIsNone(response.context["data"].conversations)

    def test_student_has_no_submission_for_non_interactive(self):
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertIsNone(response.context["data"].submission)

    def test_student_existing_answers_empty_when_none_submitted(self):
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.context["data"].existing_answers, [])

    def test_student_existing_answers_populated_after_submission(self):
        SectionAnswer.objects.create(
            user=self.student_user, section=self.ni_section, answer="Four"
        )
        SectionAnswer.objects.create(
            user=self.student_user, section=self.ni_section, answer="4"
        )
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        answers = response.context["data"].existing_answers
        self.assertEqual(len(answers), 2)
        self.assertIn("answer", answers[0])
        self.assertIn("submitted_at", answers[0])

    def test_teacher_sees_non_interactive_badge_in_response(self):
        self.client.login(username="teacher", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["data"].section_type, "non_interactive")
        self.assertContains(response, "Non-Interactive")

    def test_teacher_still_has_conversations_card(self):
        """Teachers can still test non-interactive sections via conversations."""
        self.client.login(username="teacher", password="password")
        response = self.client.get(self.url)
        self.assertContains(response, "Conversations")
