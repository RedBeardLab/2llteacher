"""
Tests for the HomeworkEditView.

This module tests the HomeworkEditView, which allows teachers to edit
existing homework assignments and their sections.
"""

import uuid
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
import datetime

from accounts.models import User, Teacher, Student
from homeworks.models import Homework, Section, SectionSolution
from homeworks.services import HomeworkUpdateResult


class HomeworkEditViewTestCase(TestCase):
    """Test the HomeworkEditView."""

    def setUp(self):
        """Set up test data."""
        # Create teacher user
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create another teacher (not the owner)
        self.other_teacher_user = User.objects.create_user(
            username="other_teacher",
            email="other_teacher@example.com",
            password="password",
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        # Create student user
        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create course
        from courses.models import Course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create homework
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

        # Set up client
        self.client = Client()

    def test_edit_view_get_teacher_access(self):
        """Test teacher can access the edit view."""
        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Access edit view
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check response is successful
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/form.html")

        # Check context data
        self.assertEqual(response.context["data"].action, "edit")
        self.assertEqual(response.context["data"].user_type, "teacher")
        self.assertEqual(response.context["data"].form.instance.id, self.homework.id)
        self.assertEqual(len(response.context["data"].section_forms.forms), 2)

    def test_edit_view_get_teacher_no_access(self):
        """Test teacher without ownership can't access the edit view."""
        # Login as other teacher
        self.client.login(username="other_teacher", password="password")

        # Access edit view
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check access is denied
        self.assertEqual(response.status_code, 403)

    def test_edit_view_get_student_no_access(self):
        """Test student cannot access the edit view."""
        # Login as student
        self.client.login(username="student", password="password")

        # Access edit view
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check access is denied
        self.assertEqual(response.status_code, 403)

    def test_edit_view_invalid_homework(self):
        """Test accessing non-existent homework redirects to list."""
        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Access non-existent homework
        url = reverse("homeworks:edit", kwargs={"homework_id": uuid.uuid4()})
        response = self.client.get(url)

        # Check redirection
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("homeworks:list"))

    @patch("homeworks.services.HomeworkService.update_homework")
    def test_edit_view_post_success(self, mock_update_homework):
        """Test successful homework update."""
        # Mock successful update
        mock_update_homework.return_value = HomeworkUpdateResult(
            success=True,
            homework_id=self.homework.id,
            updated_section_ids=[self.section_without_solution.id],
            created_section_ids=[uuid.uuid4()],
            deleted_section_ids=[],
        )

        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Prepare post data
        post_data = {
            "title": "Updated Homework Title",
            "description": "Updated description",
            "due_date": "2030-02-01T00:00:00",
            "llm_config": "",
            "sections-TOTAL_FORMS": "2",
            "sections-INITIAL_FORMS": "2",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": self.section_without_solution.id,
            "sections-0-title": "Updated Section Title",
            "sections-0-content": "Updated content",
            "sections-0-order": "1",
            "sections-0-solution": "New solution",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "2",
            "sections-1-solution": self.section_with_solution.solution.content,
        }

        # Submit the form
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.post(url, post_data)

        # Check redirection to detail view
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("homeworks:detail", kwargs={"homework_id": self.homework.id}),
        )

        # Verify mock was called with expected data
        mock_update_homework.assert_called_once()
        # Only checking first arg which is the homework id
        self.assertEqual(mock_update_homework.call_args[0][0], self.homework.id)

    @patch("homeworks.services.HomeworkService.update_homework")
    def test_edit_view_post_service_error(self, mock_update_homework):
        """Test service error handling."""
        # Mock service error
        mock_update_homework.return_value = HomeworkUpdateResult(
            success=False, error="Test service error", homework_id=None
        )

        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Prepare post data
        post_data = {
            "title": "Updated Homework Title",
            "description": "Updated description",
            "due_date": "2030-02-01T00:00:00",
            "llm_config": "",
            "sections-TOTAL_FORMS": "2",
            "sections-INITIAL_FORMS": "2",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": self.section_without_solution.id,
            "sections-0-title": "Updated Section Title",
            "sections-0-content": "Updated content",
            "sections-0-order": "1",
            "sections-0-solution": "New solution",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "2",
            "sections-1-solution": self.section_with_solution.solution.content,
        }

        # Submit the form
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.post(url, post_data)

        # Check form is re-rendered with error
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/form.html")
        self.assertEqual(response.context["data"].is_submitted, False)

    def test_edit_view_post_form_validation_error(self):
        """Test form validation error handling."""
        # Login as teacher
        self.client.login(username="teacher", password="password")

        # Prepare invalid post data (missing required fields)
        post_data = {
            "title": "",  # Empty title should fail validation
            "description": "Updated description",
            "due_date": "2020-01-01T00:00:00",  # Past date should fail validation
            "llm_config": "",
            "sections-TOTAL_FORMS": "2",
            "sections-INITIAL_FORMS": "2",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": self.section_without_solution.id,
            "sections-0-title": "",  # Empty title should fail validation
            "sections-0-content": "Updated content",
            "sections-0-order": "1",
            "sections-0-solution": "New solution",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "1",  # Duplicate order should fail validation
            "sections-1-solution": self.section_with_solution.solution.content,
        }

        # Submit the form
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.post(url, post_data)

        # Check form is re-rendered with errors
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/form.html")
        self.assertEqual(response.context["data"].is_submitted, False)
        self.assertIsNotNone(response.context["data"].errors)
