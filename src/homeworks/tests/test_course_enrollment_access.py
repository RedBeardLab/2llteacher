"""
Tests for course enrollment-based access control.

This module tests that students can only access homeworks from courses they are enrolled in,
and are properly denied access to homeworks from other courses.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from homeworks.models import Homework, Section
from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment, CourseHomework, CourseTeacher

User = get_user_model()


class CourseEnrollmentAccessTestCase(TestCase):
    """Test that course enrollment controls homework access."""

    def setUp(self):
        """Set up test data with multiple courses and students."""
        # Create teacher
        self.teacher_user = User.objects.create_user(
            username="teacher1",
            email="teacher1@example.com",
            password="password123",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create two students
        self.student1_user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="password123",
        )
        self.student1 = Student.objects.create(user=self.student1_user)

        self.student2_user = User.objects.create_user(
            username="student2",
            email="student2@example.com",
            password="password123",
        )
        self.student2 = Student.objects.create(user=self.student2_user)

        # Create two courses
        self.course1 = Course.objects.create(
            name="Python Basics",
            code="PY101",
            description="Introduction to Python",
            is_active=True,
        )

        self.course2 = Course.objects.create(
            name="Advanced Python",
            code="PY201",
            description="Advanced Python topics",
            is_active=True,
        )

        # Add teacher to both courses
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher, role="owner"
        )
        CourseTeacher.objects.create(
            course=self.course2, teacher=self.teacher, role="owner"
        )

        # Enroll student1 in course1 only
        CourseEnrollment.objects.create(
            course=self.course1, student=self.student1, is_active=True
        )

        # Enroll student2 in course2 only
        CourseEnrollment.objects.create(
            course=self.course2, student=self.student2, is_active=True
        )

        # Create homework for course1
        self.homework1 = Homework.objects.create(
            title="Homework 1 - Variables",
            description="Learn about variables",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section1 = Section.objects.create(
            homework=self.homework1,
            title="Section 1",
            content="Content 1",
            order=1,
        )
        CourseHomework.objects.create(course=self.course1, homework=self.homework1)

        # Create homework for course2
        self.homework2 = Homework.objects.create(
            title="Homework 2 - Decorators",
            description="Learn about decorators",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section2 = Section.objects.create(
            homework=self.homework2,
            title="Section 1",
            content="Content 1",
            order=1,
        )
        CourseHomework.objects.create(course=self.course2, homework=self.homework2)

        # Create homework not assigned to any course
        self.homework_unassigned = Homework.objects.create(
            title="Homework 3 - Unassigned",
            description="Not assigned to any course",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section_unassigned = Section.objects.create(
            homework=self.homework_unassigned,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        self.client = Client()


class TestHomeworkListViewEnrollmentFiltering(CourseEnrollmentAccessTestCase):
    """Test that HomeworkListView only shows homeworks from enrolled courses."""

    def test_student_sees_only_enrolled_course_homeworks(self):
        """Test that student1 sees only homework1 (from course1)."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        homeworks = response.context["data"].homeworks

        # Should see only homework1
        self.assertEqual(len(homeworks), 1)
        self.assertEqual(homeworks[0].id, self.homework1.id)
        self.assertEqual(homeworks[0].title, "Homework 1 - Variables")

    def test_student_does_not_see_other_course_homeworks(self):
        """Test that student1 does NOT see homework2 (from course2)."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        homeworks = response.context["data"].homeworks

        # Should NOT see homework2
        homework_ids = [hw.id for hw in homeworks]
        self.assertNotIn(self.homework2.id, homework_ids)

    def test_student_does_not_see_unassigned_homeworks(self):
        """Test that students do NOT see homeworks not assigned to any course."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        homeworks = response.context["data"].homeworks

        # Should NOT see unassigned homework
        homework_ids = [hw.id for hw in homeworks]
        self.assertNotIn(self.homework_unassigned.id, homework_ids)

    def test_different_students_see_different_homeworks(self):
        """Test that different students see different homeworks based on enrollment."""
        # Student1 should see homework1
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))
        homeworks_student1 = response.context["data"].homeworks
        self.assertEqual(len(homeworks_student1), 1)
        self.assertEqual(homeworks_student1[0].id, self.homework1.id)

        # Student2 should see homework2
        self.client.logout()
        self.client.login(username="student2", password="password123")
        response = self.client.get(reverse("homeworks:list"))
        homeworks_student2 = response.context["data"].homeworks
        self.assertEqual(len(homeworks_student2), 1)
        self.assertEqual(homeworks_student2[0].id, self.homework2.id)

    def test_teacher_sees_all_their_homeworks(self):
        """Test that teachers see all homeworks they created."""
        self.client.login(username="teacher1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        homeworks = response.context["data"].homeworks

        # Should see all 3 homeworks
        self.assertEqual(len(homeworks), 3)
        homework_ids = {hw.id for hw in homeworks}
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework2.id, homework_ids)
        self.assertIn(self.homework_unassigned.id, homework_ids)


class TestHomeworkDetailViewEnrollmentAccess(CourseEnrollmentAccessTestCase):
    """Test that HomeworkDetailView blocks access to non-enrolled course homeworks."""

    def test_student_cannot_access_non_enrolled_course_homework(self):
        """Test that student1 cannot access homework2 (from course2)."""
        self.client.login(username="student1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)

        # Should be redirected (because _get_view_data returns None)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse("homeworks:list")))

    def test_student_cannot_access_unassigned_homework(self):
        """Test that students cannot access homeworks not assigned to any course."""
        self.client.login(username="student1", password="password123")
        url = reverse(
            "homeworks:detail", kwargs={"homework_id": self.homework_unassigned.id}
        )
        response = self.client.get(url)

        # Should be redirected
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse("homeworks:list")))

    def test_student_can_access_enrolled_course_homework(self):
        """Test that student1 CAN access homework1 (from enrolled course1)."""
        self.client.login(username="student1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["data"].id, self.homework1.id)

    def test_teacher_can_access_all_homeworks(self):
        """Test that teacher can access all homeworks they created."""
        self.client.login(username="teacher1", password="password123")

        # Can access homework1
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Can access homework2
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Can access unassigned homework
        url = reverse(
            "homeworks:detail", kwargs={"homework_id": self.homework_unassigned.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestSectionDetailViewEnrollmentAccess(CourseEnrollmentAccessTestCase):
    """Test that SectionDetailView blocks access to non-enrolled course sections."""

    def test_student_cannot_access_non_enrolled_course_section(self):
        """Test that student1 cannot access section from homework2 (course2)."""
        self.client.login(username="student1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework2.id, "section_id": self.section2.id},
        )
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.content)

    def test_student_cannot_access_unassigned_homework_section(self):
        """Test that students cannot access sections from unassigned homeworks."""
        self.client.login(username="student1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework_unassigned.id,
                "section_id": self.section_unassigned.id,
            },
        )
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.content)

    def test_student_can_access_enrolled_course_section(self):
        """Test that student1 CAN access section from homework1 (enrolled course1)."""
        self.client.login(username="student1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework1.id, "section_id": self.section1.id},
        )
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["data"].section_id, self.section1.id)

    def test_teacher_can_access_all_sections(self):
        """Test that teacher can access all sections from their homeworks."""
        self.client.login(username="teacher1", password="password123")

        # Can access section from homework1
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework1.id, "section_id": self.section1.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Can access section from homework2
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework2.id, "section_id": self.section2.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestInactiveEnrollmentAccess(CourseEnrollmentAccessTestCase):
    """Test that inactive course enrollments do not grant access."""

    def test_inactive_enrollment_denies_list_access(self):
        """Test that deactivating enrollment removes homework from list."""
        # Initially student1 can see homework1
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))
        homeworks = response.context["data"].homeworks
        self.assertEqual(len(homeworks), 1)

        # Deactivate enrollment
        enrollment = CourseEnrollment.objects.get(
            course=self.course1, student=self.student1
        )
        enrollment.is_active = False
        enrollment.save()

        # Now student1 should not see any homeworks
        response = self.client.get(reverse("homeworks:list"))
        homeworks = response.context["data"].homeworks
        self.assertEqual(len(homeworks), 0)

    def test_inactive_enrollment_denies_detail_access(self):
        """Test that deactivating enrollment denies homework detail access."""
        self.client.login(username="student1", password="password123")

        # Deactivate enrollment
        enrollment = CourseEnrollment.objects.get(
            course=self.course1, student=self.student1
        )
        enrollment.is_active = False
        enrollment.save()

        # Try to access homework detail
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        # Should be redirected
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse("homeworks:list")))

    def test_inactive_enrollment_denies_section_access(self):
        """Test that deactivating enrollment denies section access."""
        self.client.login(username="student1", password="password123")

        # Deactivate enrollment
        enrollment = CourseEnrollment.objects.get(
            course=self.course1, student=self.student1
        )
        enrollment.is_active = False
        enrollment.save()

        # Try to access section
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework1.id, "section_id": self.section1.id},
        )
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)


class TestMultipleCourseEnrollment(CourseEnrollmentAccessTestCase):
    """Test behavior when students are enrolled in multiple courses."""

    def test_student_enrolled_in_multiple_courses_sees_all_homeworks(self):
        """Test that student enrolled in multiple courses sees homeworks from all."""
        # Enroll student1 in course2 as well
        CourseEnrollment.objects.create(
            course=self.course2, student=self.student1, is_active=True
        )

        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        self.assertEqual(len(homeworks), 2)

        homework_ids = {hw.id for hw in homeworks}
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework2.id, homework_ids)

    def test_student_can_access_details_from_all_enrolled_courses(self):
        """Test that student can access homework details from all enrolled courses."""
        # Enroll student1 in course2 as well
        CourseEnrollment.objects.create(
            course=self.course2, student=self.student1, is_active=True
        )

        self.client.login(username="student1", password="password123")

        # Can access homework1
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Can also access homework2 now
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestStudentWithNoEnrollments(CourseEnrollmentAccessTestCase):
    """Test behavior for students not enrolled in any course."""

    def test_student_with_no_enrollments_sees_no_homeworks(self):
        """Test that student with no enrollments sees empty homework list."""
        # Create new student not enrolled anywhere
        student3_user = User.objects.create_user(
            username="student3", email="student3@example.com", password="password123"
        )
        Student.objects.create(user=student3_user)

        self.client.login(username="student3", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        self.assertEqual(len(homeworks), 0)

    def test_student_with_no_enrollments_cannot_access_any_homework(self):
        """Test that student with no enrollments cannot access any homework."""
        # Create new student not enrolled anywhere
        student3_user = User.objects.create_user(
            username="student3", email="student3@example.com", password="password123"
        )
        Student.objects.create(user=student3_user)

        self.client.login(username="student3", password="password123")

        # Try to access homework1
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Try to access homework2
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
