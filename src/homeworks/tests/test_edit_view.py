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

        # Create courses
        from courses.models import Course, CourseTeacher

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Assign first teacher to the course
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
            role="owner",
        )

        # Create a second course for the other teacher
        self.other_course = Course.objects.create(
            name="Other Course",
            code="OTHER101",
            description="Another course",
        )

        # Assign other teacher to the other course
        CourseTeacher.objects.create(
            course=self.other_course,
            teacher=self.other_teacher,
            role="owner",
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

    def test_edit_view_post_teacher_different_course_no_access(self):
        """Test teacher from a different course cannot update the homework."""
        # Login as other teacher (teaches different course)
        self.client.login(username="other_teacher", password="password")

        # Prepare post data
        post_data = {
            "title": "Trying to Update",
            "description": "Should not work",
            "due_date": "2030-02-01T00:00:00",
            "llm_config": "",
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": self.section_without_solution.id,
            "sections-0-title": "Updated Section Title",
            "sections-0-content": "Updated content",
            "sections-0-order": "1",
            "sections-0-solution": "",
        }

        # Try to submit the form
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.post(url, post_data)

        # Check access is denied
        self.assertEqual(response.status_code, 403)

        # Verify homework was NOT updated
        self.homework.refresh_from_db()
        self.assertEqual(self.homework.title, "Test Homework")
        self.assertNotEqual(self.homework.title, "Trying to Update")

    def test_edit_view_teacher_teaches_course_can_edit(self):
        """Test teacher who teaches the course can edit homework even if they didn't create it."""
        from courses.models import CourseTeacher

        # Add other_teacher to teach the same course
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.other_teacher,
            role="instructor",
        )

        # Login as other teacher
        self.client.login(username="other_teacher", password="password")

        # Access edit view (GET)
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check access is allowed
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/form.html")

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

        # Prepare post data (note: course is NOT included, as it's not in the edit form)
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
            "sections-0-section_type": "conversation",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "2",
            "sections-1-solution": self.section_with_solution.solution.content,
            "sections-1-section_type": "conversation",
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

        # Prepare post data (note: course is NOT included, as it's not in the edit form)
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
            "sections-0-section_type": "conversation",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "2",
            "sections-1-solution": self.section_with_solution.solution.content,
            "sections-1-section_type": "conversation",
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
        # Note: course is NOT included, as it's not in the edit form
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
            "sections-0-section_type": "conversation",
            "sections-1-id": self.section_with_solution.id,
            "sections-1-title": self.section_with_solution.title,
            "sections-1-content": self.section_with_solution.content,
            "sections-1-order": "1",  # Duplicate order should fail validation
            "sections-1-solution": self.section_with_solution.solution.content,
            "sections-1-section_type": "conversation",
        }

        # Submit the form
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})
        response = self.client.post(url, post_data)

        # Check form is re-rendered with errors
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/form.html")
        self.assertEqual(response.context["data"].is_submitted, False)
        self.assertIsNotNone(response.context["data"].errors)


class HomeworkEditSectionTypeTests(TestCase):
    """Test that section_type is preserved and updated correctly via the edit view."""

    def setUp(self):
        from courses.models import Course, CourseTeacher

        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.course = Course.objects.create(name="Course", code="C101", description="")
        CourseTeacher.objects.create(course=self.course, teacher=self.teacher, role="owner")

        self.homework = Homework.objects.create(
            title="HW",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=datetime.datetime(2030, 1, 1),
        )

        self.conv_section = Section.objects.create(
            homework=self.homework,
            title="Chat",
            content="Talk.",
            order=1,
            section_type=Section.SECTION_TYPE_CONVERSATION,
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What?",
            order=2,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

        self.url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})

    def _base_post_data(self):
        return {
            "title": "HW",
            "description": "desc",
            "due_date": "2030-02-01T00:00:00",
            "llm_config": "",
            "sections-TOTAL_FORMS": "2",
            "sections-INITIAL_FORMS": "2",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.conv_section.id),
            "sections-0-title": self.conv_section.title,
            "sections-0-content": self.conv_section.content,
            "sections-0-order": "1",
            "sections-0-solution": "",
            "sections-0-section_type": "conversation",
            "sections-1-id": str(self.ni_section.id),
            "sections-1-title": self.ni_section.title,
            "sections-1-content": self.ni_section.content,
            "sections-1-order": "2",
            "sections-1-solution": "",
            "sections-1-section_type": "non_interactive",
        }

    def test_edit_get_prepopulates_section_type(self):
        """section_type initial value is set from the existing section."""
        self.client.login(username="teacher", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        forms = response.context["data"].section_forms.forms
        self.assertEqual(forms[0].initial.get("section_type"), "conversation")
        self.assertEqual(forms[1].initial.get("section_type"), "non_interactive")

    def test_edit_post_updates_section_type(self):
        """Changing section_type via POST updates the section."""
        self.client.login(username="teacher", password="password")
        data = self._base_post_data()
        data["sections-0-section_type"] = "non_interactive"  # flip conversation → non_interactive

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

        self.conv_section.refresh_from_db()
        self.assertEqual(self.conv_section.section_type, "non_interactive")

    def test_edit_post_preserves_section_type(self):
        """Existing section_type is preserved when not changed."""
        self.client.login(username="teacher", password="password")
        response = self.client.post(self.url, self._base_post_data())
        self.assertEqual(response.status_code, 302)

        self.conv_section.refresh_from_db()
        self.ni_section.refresh_from_db()
        self.assertEqual(self.conv_section.section_type, "conversation")
        self.assertEqual(self.ni_section.section_type, "non_interactive")
