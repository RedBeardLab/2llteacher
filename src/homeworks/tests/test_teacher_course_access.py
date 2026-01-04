"""
Tests for teacher access control based on course membership.

This module tests teacher access to homeworks based on which courses they teach:
- Teachers can see/edit homeworks from courses they teach
- Teachers cannot see/edit homeworks from courses they don't teach
- Teachers can see/edit homeworks they created (regardless of course assignment)
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from homeworks.models import Homework, Section
from homeworks.views import HomeworkListView, HomeworkEditView
from accounts.models import Teacher
from courses.models import Course, CourseTeacher

User = get_user_model()


class TeacherCourseAccessTestCase(TestCase):
    """Base test case for teacher course access tests."""

    def setUp(self):
        """Set up test data with multiple teachers and courses."""
        # Create three teachers
        self.teacher1_user = User.objects.create_user(
            username="teacher1",
            email="teacher1@example.com",
            password="password123",
        )
        self.teacher1 = Teacher.objects.create(user=self.teacher1_user)

        self.teacher2_user = User.objects.create_user(
            username="teacher2",
            email="teacher2@example.com",
            password="password123",
        )
        self.teacher2 = Teacher.objects.create(user=self.teacher2_user)

        self.teacher3_user = User.objects.create_user(
            username="teacher3",
            email="teacher3@example.com",
            password="password123",
        )
        self.teacher3 = Teacher.objects.create(user=self.teacher3_user)

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

        # Teacher1 is owner of course1
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher1, role="owner"
        )

        # Teacher2 is co-teacher of course1
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher2, role="co_teacher"
        )

        # Teacher2 is also owner of course2
        CourseTeacher.objects.create(
            course=self.course2, teacher=self.teacher2, role="owner"
        )

        # Create a third course for teacher3's homework
        self.course3 = Course.objects.create(
            name="Course 3",
            code="COURSE3",
            description="Course 3 description",
            is_active=True,
        )

        # Teacher3 is owner of course3
        CourseTeacher.objects.create(
            course=self.course3, teacher=self.teacher3, role="owner"
        )

        # Create homework1 by teacher1, assigned to course1 (direct FK relationship)
        self.homework1 = Homework.objects.create(
            title="Homework 1 - Variables",
            description="Learn about variables",
            created_by=self.teacher1,
            course=self.course1,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section1 = Section.objects.create(
            homework=self.homework1,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        # Create homework2 by teacher2, assigned to course2 (direct FK relationship)
        self.homework2 = Homework.objects.create(
            title="Homework 2 - Decorators",
            description="Learn about decorators",
            created_by=self.teacher2,
            course=self.course2,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section2 = Section.objects.create(
            homework=self.homework2,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        # Create homework3 by teacher3, assigned to course3 (direct FK relationship)
        self.homework3 = Homework.objects.create(
            title="Homework 3 - Unassigned",
            description="Not assigned to teacher1 or teacher2 courses",
            created_by=self.teacher3,
            course=self.course3,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section3 = Section.objects.create(
            homework=self.homework3,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        # Create homework4 by teacher1, assigned to course2 (direct FK - cross-course scenario)
        self.homework4 = Homework.objects.create(
            title="Homework 4 - Cross-Course",
            description="Created by teacher1 but assigned to course2",
            created_by=self.teacher1,
            course=self.course2,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section4 = Section.objects.create(
            homework=self.homework4,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        self.client = Client()


class TestTeacherHomeworkListViewCourseAccess(TeacherCourseAccessTestCase):
    """Test that teachers see homeworks from courses they teach."""

    def test_teacher_sees_homeworks_from_their_courses(self):
        """Test that teacher1 sees homeworks from course1."""
        self.client.login(username="teacher1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        homework_ids = {hw.id for hw in homeworks}

        # Should see homework1 (created by them, in course1) and homework4 (created by them)
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework4.id, homework_ids)

    def test_coteacher_sees_homeworks_from_course(self):
        """Test that teacher2 (co-teacher in course1) sees homework1."""
        self.client.login(username="teacher2", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        homework_ids = {hw.id for hw in homeworks}

        # Should see homework1 (from course1 where they're co-teacher)
        # homework2 (created by them, in course2 where they're owner)
        # homework4 (from course2 where they're owner)
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework2.id, homework_ids)
        self.assertIn(self.homework4.id, homework_ids)

    def test_teacher_sees_own_unassigned_homework(self):
        """Test that teacher sees their own homework even if not assigned to course."""
        self.client.login(username="teacher3", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        homework_ids = {hw.id for hw in homeworks}

        # Should see homework3 (created by them, even though not assigned to any course)
        self.assertIn(self.homework3.id, homework_ids)
        # Should only see homework3
        self.assertEqual(len(homeworks), 1)

    def test_teacher_does_not_see_homeworks_from_other_courses(self):
        """Test that teacher1 does NOT see homework2 (from course2)."""
        self.client.login(username="teacher1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        homeworks = response.context["data"].homeworks
        homework_ids = {hw.id for hw in homeworks}

        # Should NOT see homework2 (from course2 where they don't teach)
        self.assertNotIn(self.homework2.id, homework_ids)


class TestTeacherHomeworkDetailViewPermissions(TeacherCourseAccessTestCase):
    """Test teacher permissions in homework detail view."""

    def test_teacher_can_edit_homework_from_their_course(self):
        """Test that teacher1 can edit homework1 (from course1)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["data"].can_edit)

    def test_coteacher_can_edit_homework_from_course(self):
        """Test that teacher2 (co-teacher) can edit homework1 from course1."""
        self.client.login(username="teacher2", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["data"].can_edit)

    def test_teacher_cannot_edit_homework_from_other_course(self):
        """Test that teacher1 cannot edit homework2 (from course2 they don't teach)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["data"].can_edit)

    def test_teacher_can_edit_own_homework_in_other_course(self):
        """Test that teacher1 can edit homework4 (created by them, assigned to course2)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework4.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Can edit because they created it
        self.assertTrue(response.context["data"].can_edit)


class TestTeacherSectionDetailViewAccess(TeacherCourseAccessTestCase):
    """Test teacher access to section detail view."""

    def test_teacher_can_access_section_from_their_course(self):
        """Test that teacher1 can access section from course1."""
        self.client.login(username="teacher1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework1.id, "section_id": self.section1.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_coteacher_can_access_section_from_course(self):
        """Test that teacher2 (co-teacher) can access section from course1."""
        self.client.login(username="teacher2", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework1.id, "section_id": self.section1.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_access_section_from_other_course(self):
        """Test that teacher1 cannot access section from course2."""
        self.client.login(username="teacher1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework2.id, "section_id": self.section2.id},
        )
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_access_section_from_own_homework_in_other_course(self):
        """Test that teacher1 can access section from homework4 (they created it)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.homework4.id, "section_id": self.section4.id},
        )
        response = self.client.get(url)

        # Can access because they created the homework
        self.assertEqual(response.status_code, 200)


class TestTeacherEditViewAccess(TeacherCourseAccessTestCase):
    """Test teacher access to edit view."""

    def test_teacher_can_edit_homework_from_their_course(self):
        """Test that teacher1 can edit homework from course1."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_coteacher_can_edit_homework_from_course(self):
        """Test that teacher2 (co-teacher) can edit homework from course1."""
        self.client.login(username="teacher2", password="password123")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_edit_homework_from_other_course(self):
        """Test that teacher1 cannot edit homework from course2."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_edit_own_homework_in_other_course(self):
        """Test that teacher1 can edit homework4 (they created it, in course2)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.homework4.id})
        response = self.client.get(url)

        # Can edit because they created it
        self.assertEqual(response.status_code, 200)

    def test_can_teacher_edit_homework_helper_method(self):
        """Test the _can_teacher_edit_homework helper method directly."""
        view = HomeworkEditView()

        # Teacher1 can edit homework1 (they created it)
        self.assertTrue(view._can_teacher_edit_homework(self.teacher1, self.homework1))

        # Teacher2 can edit homework1 (co-teacher in course1)
        self.assertTrue(view._can_teacher_edit_homework(self.teacher2, self.homework1))

        # Teacher1 cannot edit homework2 (from course2 they don't teach)
        self.assertFalse(view._can_teacher_edit_homework(self.teacher1, self.homework2))

        # Teacher3 cannot edit homework1 (not in any course)
        self.assertFalse(view._can_teacher_edit_homework(self.teacher3, self.homework1))

        # Teacher3 can edit homework3 (they created it)
        self.assertTrue(view._can_teacher_edit_homework(self.teacher3, self.homework3))


class TestTeacherDeletePermissions(TeacherCourseAccessTestCase):
    """Test teacher permissions for deleting homeworks."""

    def test_teacher_can_delete_homework_from_their_course(self):
        """Test that teacher1 can delete homework from course1."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.post(url, {"action": "delete"})

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Homework.objects.filter(id=self.homework1.id).exists())

    def test_coteacher_can_delete_homework_from_course(self):
        """Test that teacher2 (co-teacher) can delete homework from course1."""
        self.client.login(username="teacher2", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework1.id})
        response = self.client.post(url, {"action": "delete"})

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Homework.objects.filter(id=self.homework1.id).exists())

    def test_teacher_cannot_delete_homework_from_other_course(self):
        """Test that teacher1 cannot delete homework from course2."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework2.id})
        response = self.client.post(url, {"action": "delete"})

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        # Homework should still exist
        self.assertTrue(Homework.objects.filter(id=self.homework2.id).exists())


class TestTeacherSubmissionsViewAccess(TeacherCourseAccessTestCase):
    """Test teacher access to submissions view."""

    def test_teacher_can_view_submissions_from_their_course(self):
        """Test that teacher1 can view submissions for homework from course1."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_coteacher_can_view_submissions_from_course(self):
        """Test that teacher2 (co-teacher) can view submissions from course1."""
        self.client.login(username="teacher2", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_view_submissions_from_other_course(self):
        """Test that teacher1 cannot view submissions from course2."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework2.id})
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_view_submissions_for_own_homework_in_other_course(self):
        """Test that teacher1 can view submissions for homework4 (they created it)."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework4.id})
        response = self.client.get(url)

        # Can view because they created it
        self.assertEqual(response.status_code, 200)


class TestTeacherRoleInCourse(TeacherCourseAccessTestCase):
    """Test that both owner and co-teacher have same access rights."""

    def test_owner_and_coteacher_have_same_access_rights(self):
        """Test that owner and co-teacher have same permissions for homework in course."""
        # Create homework by someone else, assigned to course1
        other_teacher_user = User.objects.create_user(
            username="other", email="other@example.com", password="password123"
        )
        other_teacher = Teacher.objects.create(user=other_teacher_user)

        homework_other = Homework.objects.create(
            title="Homework by Other",
            description="Created by another teacher",
            created_by=other_teacher,
            course=self.course1,
            due_date=timezone.now() + timedelta(days=7),
        )
        Section.objects.create(
            homework=homework_other,
            title="Section 1",
            content="Content 1",
            order=1,
        )

        # Both teacher1 (owner) and teacher2 (co-teacher) should see this homework
        self.client.login(username="teacher1", password="password123")
        response = self.client.get(reverse("homeworks:list"))
        homework_ids_teacher1 = {hw.id for hw in response.context["data"].homeworks}
        self.assertIn(homework_other.id, homework_ids_teacher1)

        self.client.logout()
        self.client.login(username="teacher2", password="password123")
        response = self.client.get(reverse("homeworks:list"))
        homework_ids_teacher2 = {hw.id for hw in response.context["data"].homeworks}
        self.assertIn(homework_other.id, homework_ids_teacher2)

        # Both should be able to edit
        url = reverse("homeworks:detail", kwargs={"homework_id": homework_other.id})

        self.client.logout()
        self.client.login(username="teacher1", password="password123")
        response = self.client.get(url)
        self.assertTrue(response.context["data"].can_edit)

        self.client.logout()
        self.client.login(username="teacher2", password="password123")
        response = self.client.get(url)
        self.assertTrue(response.context["data"].can_edit)
