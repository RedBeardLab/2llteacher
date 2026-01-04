"""
Tests for the HomeworkDetailView.

This module tests the behavior of the HomeworkDetailView, including
permissions, data preparation, and error handling.
"""

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import uuid

from homeworks.models import Homework, Section, SectionSolution
from homeworks.views import HomeworkDetailView, HomeworkDetailData
from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment, CourseTeacher

User = get_user_model()


class HomeworkDetailViewTests(TestCase):
    """Tests for the HomeworkDetailView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.teacher_user = User.objects.create_user(
            username="testteacher",
            email="teacher@example.com",
            password="password123",
            first_name="Test",
            last_name="Teacher",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.other_teacher_user = User.objects.create_user(
            username="otherteacher", email="other@example.com", password="password123"
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
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

        # Create homework with course (direct FK relationship)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        # Create a solution
        self.solution = SectionSolution.objects.create(content="Test solution content")

        # Create sections for the homework
        self.section1 = Section.objects.create(
            homework=self.homework,
            title="Section 1",
            content="Test content for section 1",
            order=1,
            solution=self.solution,
        )

        self.section2 = Section.objects.create(
            homework=self.homework,
            title="Section 2",
            content="Test content for section 2",
            order=2,
        )

        # Create the request factory
        self.factory = RequestFactory()

    def test_get_view_data_for_owner_teacher(self):
        """Test the _get_view_data method for a teacher who owns the homework."""
        view = HomeworkDetailView()
        data = view._get_view_data(self.teacher_user, self.homework.id)

        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkDetailData)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "teacher")

        # Check if edit permission is correctly set
        self.assertTrue(data.can_edit)

        # Check homework details
        self.assertEqual(data.title, self.homework.title)
        self.assertEqual(data.description, self.homework.description)
        self.assertEqual(str(data.created_by), str(self.teacher.id))

        # Check teacher name is correctly displayed
        self.assertEqual(data.created_by_name, "Test Teacher")

        # Check sections data
        self.assertEqual(len(data.sections), 2)
        self.assertEqual(data.sections[0].title, self.section1.title)
        self.assertEqual(data.sections[1].title, self.section2.title)

        # Check solution data
        self.assertTrue(data.sections[0].has_solution)
        self.assertEqual(data.sections[0].solution_content, self.solution.content)
        self.assertFalse(data.sections[1].has_solution)
        self.assertIsNone(data.sections[1].solution_content)

    def test_get_view_data_for_other_teacher(self):
        """Test the _get_view_data method for a teacher who doesn't own the homework."""
        view = HomeworkDetailView()
        data = view._get_view_data(self.other_teacher_user, self.homework.id)

        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkDetailData)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "teacher")

        # Check if edit permission is correctly set (should be False)
        self.assertFalse(data.can_edit)

    def test_get_view_data_for_student(self):
        """Test the _get_view_data method for a student user."""
        view = HomeworkDetailView()
        data = view._get_view_data(self.student_user, self.homework.id)

        # Check if data is of the correct type
        self.assertIsInstance(data, HomeworkDetailData)

        # Check if the user type is correctly identified
        self.assertEqual(data.user_type, "student")

        # Check if edit permission is correctly set (should be False)
        self.assertFalse(data.can_edit)

        # Check if sections are included but without solutions
        self.assertEqual(len(data.sections), 2)

    def test_get_view_data_nonexistent_homework(self):
        """Test the _get_view_data method for a non-existent homework."""
        view = HomeworkDetailView()
        data = view._get_view_data(self.teacher_user, uuid.uuid4())

        # Should return None for non-existent homework
        self.assertIsNone(data)

    def test_get_request_as_owner_teacher(self):
        """Test handling a GET request as the teacher who owns the homework."""
        # Login as teacher
        self.client.login(username="testteacher", password="password123")

        # Get the response
        response = self.client.get(reverse("homeworks:detail", args=[self.homework.id]))

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check template used
        self.assertTemplateUsed(response, "homeworks/detail.html")

        # Check context data
        self.assertIn("data", response.context)
        data = response.context["data"]
        self.assertEqual(data.user_type, "teacher")
        self.assertTrue(data.can_edit)

    def test_get_request_nonexistent_homework(self):
        """Test handling a GET request for a non-existent homework."""
        # Login as teacher
        self.client.login(username="testteacher", password="password123")

        # Get the response for a non-existent homework
        response = self.client.get(reverse("homeworks:detail", args=[uuid.uuid4()]))

        # Should redirect to the list view
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("homeworks:list"))
