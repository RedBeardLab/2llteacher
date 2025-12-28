"""
Tests for the homeworks app views.

This module tests the views in the homeworks app, focusing on testing
the behavior of the views and ensuring they correctly process and display data.
"""

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from unittest.mock import patch, MagicMock
import uuid

from homeworks.models import Homework, Section
from homeworks.views import HomeworkListView, HomeworkListData
from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment, CourseHomework, CourseTeacher

User = get_user_model()


class HomeworkListViewTests(TestCase):
    """Tests for the HomeworkListView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a sample homework
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        # Create sections for the homework
        self.section1 = Section.objects.create(
            homework=self.homework,
            title="Section 1",
            content="Test content for section 1",
            order=1,
        )

        self.section2 = Section.objects.create(
            homework=self.homework,
            title="Section 2",
            content="Test content for section 2",
            order=2,
        )

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

        # Assign homework to course
        CourseHomework.objects.create(course=self.course, homework=self.homework)

        # Create the request factory
        self.factory = RequestFactory()

    def test_get_view_data_for_teacher(self):
        """Test the _get_view_data method for a teacher user."""
        view = HomeworkListView()
        data = view._get_view_data(self.teacher_user)

        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkListData)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "teacher")

        # Check if the homework is included
        self.assertEqual(len(data.homeworks), 1)
        self.assertEqual(data.homeworks[0].id, self.homework.id)
        self.assertEqual(data.homeworks[0].title, self.homework.title)
        self.assertEqual(data.homeworks[0].section_count, 2)

        # Check if section data is not included for teacher view
        self.assertIsNone(data.homeworks[0].sections)
        self.assertFalse(data.has_progress_data)

    @patch("homeworks.services.HomeworkService.get_student_homework_progress")
    def test_get_view_data_for_student(self, mock_get_progress):
        """Test the _get_view_data method for a student user."""
        # Mock the progress service
        mock_progress_data = MagicMock()
        mock_progress_data.sections_progress = [
            MagicMock(
                section_id=self.section1.id,
                title=self.section1.title,
                order=self.section1.order,
                status="submitted",
                conversation_id=uuid.uuid4(),
            ),
            MagicMock(
                section_id=self.section2.id,
                title=self.section2.title,
                order=self.section2.order,
                status="not_started",
                conversation_id=None,
            ),
        ]
        mock_get_progress.return_value = mock_progress_data

        view = HomeworkListView()
        data = view._get_view_data(self.student_user)

        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkListData)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "student")

        # Check if the homework is included
        self.assertEqual(len(data.homeworks), 1)

        # Check if section data is included for student view
        self.assertTrue(data.has_progress_data)
        self.assertIsNotNone(data.homeworks[0].sections)
        self.assertEqual(len(data.homeworks[0].sections), 2)

        # Check one section detail
        self.assertEqual(data.homeworks[0].sections[0].status, "submitted")
        self.assertEqual(data.homeworks[0].sections[1].status, "not_started")

    def test_get_view_data_for_unknown_user(self):
        """Test the _get_view_data method for an unknown user type."""
        unknown_user = User.objects.create_user(
            username="unknown", email="unknown@example.com", password="password123"
        )

        view = HomeworkListView()
        data = view._get_view_data(unknown_user)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "unknown")

        # Check if no homeworks are returned
        self.assertEqual(len(data.homeworks), 0)

    def test_get_request_as_teacher(self):
        """Test handling a GET request as a teacher."""
        # Login as teacher
        self.client.login(username="testteacher", password="password123")

        # Get the response
        response = self.client.get(reverse("homeworks:list"))

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check template used
        self.assertTemplateUsed(response, "homeworks/list.html")

        # Check context data
        self.assertIn("data", response.context)
        data = response.context["data"]
        self.assertEqual(data.user_type, "teacher")
        self.assertEqual(len(data.homeworks), 1)

    def test_get_request_as_student(self):
        """Test handling a GET request as a student."""
        # Login as student
        self.client.login(username="teststudent", password="password123")

        # Get the response
        response = self.client.get(reverse("homeworks:list"))

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check template used
        self.assertTemplateUsed(response, "homeworks/list.html")

        # Check context data
        self.assertIn("data", response.context)
        data = response.context["data"]
        self.assertEqual(data.user_type, "student")
        self.assertEqual(len(data.homeworks), 1)

    def test_get_request_unauthenticated(self):
        """Test handling a GET request when user is not authenticated."""
        # Get the response (without logging in)
        response = self.client.get(reverse("homeworks:list"))

        # Check that user is redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))
