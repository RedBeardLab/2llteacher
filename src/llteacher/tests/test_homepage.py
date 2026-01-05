"""
Tests for the homepage view.

This module tests the homepage view's redirect logic for students
based on their course enrollment status.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment

User = get_user_model()


class HomepageRedirectTests(TestCase):
    """Tests for homepage redirect logic based on user type and enrollment."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create teacher user
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create student user
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )

    def test_unauthenticated_user_sees_homepage(self):
        """Test that unauthenticated users see the homepage."""
        response = self.client.get("/")

        # Should render the homepage template, not redirect
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage.html")

    def test_teacher_sees_homepage(self):
        """Test that teachers see the homepage normally."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get("/")

        # Should render the homepage template, not redirect
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage.html")

    def test_student_with_no_enrollments_redirected_to_courses(self):
        """Test that students with no course enrollments are redirected to /courses/."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get("/")

        # Should redirect to courses page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/courses/")

    def test_student_with_active_enrollment_redirected_to_homeworks(self):
        """Test that students with active enrollments are redirected to /homeworks/."""
        # Enroll student in course
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.get("/")

        # Should redirect to homeworks page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/homeworks/")

    def test_student_with_inactive_enrollment_redirected_to_courses(self):
        """Test that students with only inactive enrollments are redirected to /courses/."""
        # Create inactive enrollment
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=False
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.get("/")

        # Should redirect to courses page (inactive doesn't count)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/courses/")

    def test_student_with_multiple_active_enrollments_redirected_to_homeworks(self):
        """Test that students with multiple enrollments are redirected to /homeworks/."""
        # Create multiple courses
        course2 = Course.objects.create(
            name="Another Course",
            code="TEST102",
            description="Another test course",
            is_active=True,
        )

        # Enroll in both courses
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )
        CourseEnrollment.objects.create(
            course=course2, student=self.student, is_active=True
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.get("/")

        # Should redirect to homeworks page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/homeworks/")

    def test_student_with_mixed_enrollments_redirected_to_homeworks(self):
        """Test that students with at least one active enrollment are redirected to /homeworks/."""
        # Create another course
        course2 = Course.objects.create(
            name="Another Course",
            code="TEST102",
            description="Another test course",
            is_active=True,
        )

        # Create one active and one inactive enrollment
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )
        CourseEnrollment.objects.create(
            course=course2, student=self.student, is_active=False
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.get("/")

        # Should redirect to homeworks page (has at least one active)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/homeworks/")
