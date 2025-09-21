"""
Tests for permission decorators.

This module contains tests for the permission decorators used to control
access to views based on user roles and object ownership.
"""

from uuid import uuid4
from unittest.mock import Mock, patch

from django.test import TestCase, RequestFactory
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model

from llteacher.permissions.decorators import (
    get_teacher_or_student,
    teacher_required,
    student_required,
    homework_owner_required,
    section_access_required,
)

User = get_user_model()


class GetTeacherOrStudentTests(TestCase):
    """Tests for get_teacher_or_student function."""

    def test_user_with_teacher_profile(self):
        """Test that function returns teacher profile when available."""
        # Create mock user with teacher profile
        user = Mock()
        teacher_profile = Mock()
        user.teacher_profile = teacher_profile
        user.student_profile = None

        # Get profiles
        teacher, student = get_teacher_or_student(user)

        # Verify results
        self.assertEqual(teacher, teacher_profile)
        self.assertIsNone(student)

    def test_user_with_student_profile(self):
        """Test that function returns student profile when available."""
        # Create mock user with student profile
        user = Mock()
        user.teacher_profile = None
        student_profile = Mock()
        user.student_profile = student_profile

        # Get profiles
        teacher, student = get_teacher_or_student(user)

        # Verify results
        self.assertIsNone(teacher)
        self.assertEqual(student, student_profile)

    def test_user_with_both_profiles(self):
        """Test that function returns both profiles when available."""
        # Create mock user with both profiles
        user = Mock()
        teacher_profile = Mock()
        student_profile = Mock()
        user.teacher_profile = teacher_profile
        user.student_profile = student_profile

        # Get profiles
        teacher, student = get_teacher_or_student(user)

        # Verify results
        self.assertEqual(teacher, teacher_profile)
        self.assertEqual(student, student_profile)

    def test_user_with_no_profiles(self):
        """Test that function returns None for both profiles when not available."""
        # Create mock user with no profiles
        user = Mock()
        user.teacher_profile = None
        user.student_profile = None

        # Get profiles
        teacher, student = get_teacher_or_student(user)

        # Verify results
        self.assertIsNone(teacher)
        self.assertIsNone(student)


class TeacherRequiredTests(TestCase):
    """Tests for teacher_required decorator."""

    def setUp(self):
        self.factory = RequestFactory()

        # Create a simple view function
        @teacher_required
        def test_view(request):
            return HttpResponse("Access granted")

        self.test_view = test_view

    def test_teacher_access_granted(self):
        """Test that teachers can access the view."""
        # Create request with user who has teacher profile
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = Mock()

        # Call the decorated view
        response = self.test_view(request)

        # Verify access granted
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Access granted")

    def test_non_teacher_access_denied(self):
        """Test that non-teachers cannot access the view."""
        # Create request with user who does not have teacher profile
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = None

        # Call the decorated view
        response = self.test_view(request)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)


class StudentRequiredTests(TestCase):
    """Tests for student_required decorator."""

    def setUp(self):
        self.factory = RequestFactory()

        # Create a simple view function
        @student_required
        def test_view(request):
            return HttpResponse("Access granted")

        self.test_view = test_view

    def test_student_access_granted(self):
        """Test that students can access the view."""
        # Create request with user who has student profile
        request = self.factory.get("/")
        request.user = Mock()
        request.user.student_profile = Mock()

        # Call the decorated view
        response = self.test_view(request)

        # Verify access granted
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Access granted")

    def test_non_student_access_denied(self):
        """Test that non-students cannot access the view."""
        # Create request with user who does not have student profile
        request = self.factory.get("/")
        request.user = Mock()
        request.user.student_profile = None

        # Call the decorated view
        response = self.test_view(request)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)


class HomeworkOwnerRequiredTests(TestCase):
    """Tests for homework_owner_required decorator."""

    def setUp(self):
        self.factory = RequestFactory()

        # Create a simple view function
        @homework_owner_required
        def test_view(request, homework):
            return HttpResponse(f"Access granted to {homework.title}")

        self.test_view = test_view

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_owner_access_granted(self, mock_get_object):
        """Test that homework owner can access the view."""
        # Create mock homework and teacher
        homework = Mock()
        homework.title = "Test Homework"
        teacher_profile = Mock()

        # Set up mock to return the homework
        mock_get_object.return_value = homework

        # Create request with user who is the homework owner
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = teacher_profile

        # Set the teacher as the homework creator
        homework.created_by = teacher_profile

        # Call the decorated view
        homework_id = uuid4()
        response = self.test_view(request, homework_id)

        # Verify access granted
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Access granted to Test Homework")

        # Verify mock was called correctly
        mock_get_object.assert_called_once()

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_non_owner_access_denied(self, mock_get_object):
        """Test that non-owner cannot access the view."""
        # Create mock homework and teachers
        homework = Mock()
        teacher_profile = Mock()
        other_teacher_profile = Mock()

        # Set up mock to return the homework
        mock_get_object.return_value = homework

        # Create request with user who is not the homework owner
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = teacher_profile

        # Set a different teacher as the homework creator
        homework.created_by = other_teacher_profile

        # Call the decorated view
        homework_id = uuid4()
        response = self.test_view(request, homework_id)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_non_teacher_access_denied(self, mock_get_object):
        """Test that non-teacher cannot access the view."""
        # Create mock homework
        homework = Mock()

        # Set up mock to return the homework
        mock_get_object.return_value = homework

        # Create request with user who is not a teacher
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = None

        # Call the decorated view
        homework_id = uuid4()
        response = self.test_view(request, homework_id)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)


class SectionAccessRequiredTests(TestCase):
    """Tests for section_access_required decorator."""

    def setUp(self):
        self.factory = RequestFactory()

        # Create a simple view function
        @section_access_required
        def test_view(request, section):
            return HttpResponse(f"Access granted to {section.title}")

        self.test_view = test_view

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_teacher_owner_access_granted(self, mock_get_object):
        """Test that teacher who owns the homework can access the section."""
        # Create mock section, homework and teacher
        section = Mock()
        section.title = "Test Section"
        homework = Mock()
        section.homework = homework
        teacher_profile = Mock()

        # Set up mock to return the section
        mock_get_object.return_value = section

        # Create request with user who is the homework owner
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = teacher_profile
        request.user.student_profile = None

        # Set the teacher as the homework creator
        homework.created_by = teacher_profile

        # Call the decorated view
        section_id = uuid4()
        response = self.test_view(request, section_id)

        # Verify access granted
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Access granted to Test Section")

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_student_access_granted(self, mock_get_object):
        """Test that any student can access the section."""
        # Create mock section
        section = Mock()
        section.title = "Test Section"
        section.homework = Mock()

        # Set up mock to return the section
        mock_get_object.return_value = section

        # Create request with student user
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = None
        request.user.student_profile = Mock()

        # Call the decorated view
        section_id = uuid4()
        response = self.test_view(request, section_id)

        # Verify access granted
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Access granted to Test Section")

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_non_owner_teacher_access_denied(self, mock_get_object):
        """Test that teacher who doesn't own the homework cannot access the section."""
        # Create mock section, homework, and teachers
        section = Mock()
        section.title = "Test Section"
        homework = Mock()
        section.homework = homework
        teacher_profile = Mock()
        other_teacher_profile = Mock()

        # Set up mock to return the section
        mock_get_object.return_value = section

        # Create request with teacher who is not the homework owner
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = teacher_profile
        request.user.student_profile = None

        # Set a different teacher as the homework creator
        homework.created_by = other_teacher_profile

        # Call the decorated view
        section_id = uuid4()
        response = self.test_view(request, section_id)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)

    @patch("llteacher.permissions.decorators.get_object_or_404")
    def test_non_teacher_non_student_access_denied(self, mock_get_object):
        """Test that user who is neither teacher nor student cannot access the section."""
        # Create mock section
        section = Mock()
        section.homework = Mock()

        # Set up mock to return the section
        mock_get_object.return_value = section

        # Create request with user who is neither teacher nor student
        request = self.factory.get("/")
        request.user = Mock()
        request.user.teacher_profile = None
        request.user.student_profile = None

        # Call the decorated view
        section_id = uuid4()
        response = self.test_view(request, section_id)

        # Verify access denied
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, HttpResponseForbidden)
