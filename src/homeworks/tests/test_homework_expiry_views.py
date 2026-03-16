"""
Tests for homework expiry/visibility enforcement in views.

Covers:
- HomeworkListView: expired/hidden homeworks hidden from students, visible to teachers
- HomeworkDetailView: students blocked when inaccessible; teachers always see it
- SectionDetailView: students blocked when homework is inaccessible
- HomeworkForm validation: expires_at must be after due_date
"""

from datetime import timedelta

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment, CourseTeacher
from homeworks.models import Homework, Section
from homeworks.views import HomeworkListView
from homeworks.forms import HomeworkCreateForm, HomeworkEditForm

User = get_user_model()


class HomeworkExpiryViewSetUpMixin(TestCase):
    """Shared setUp for expiry view tests."""

    def setUp(self):
        self.factory = RequestFactory()

        # Teacher
        teacher_user = User.objects.create_user(
            username="teacher", email="t@test.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=teacher_user)
        self.teacher_user = teacher_user

        # Student
        student_user = User.objects.create_user(
            username="student", email="s@test.com", password="pass"
        )
        self.student = Student.objects.create(user=student_user)
        self.student_user = student_user

        # Course
        self.course = Course.objects.create(name="Course", code="C1", is_active=True)
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        # Visible homework (control)
        self.visible_hw = Homework.objects.create(
            title="Visible",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        # Hidden homework (manual toggle)
        self.hidden_hw = Homework.objects.create(
            title="Hidden",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            is_hidden=True,
        )

        # Expired homework
        self.expired_hw = Homework.objects.create(
            title="Expired",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() - timedelta(days=14),
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Section for visible homework
        self.section = Section.objects.create(
            homework=self.visible_hw,
            title="Section 1",
            content="content",
            order=1,
        )

        # Section for expired homework
        self.expired_section = Section.objects.create(
            homework=self.expired_hw,
            title="Section 1",
            content="content",
            order=1,
        )


# ─── HomeworkListView ─────────────────────────────────────────────────────────


class HomeworkListViewExpiryTests(HomeworkExpiryViewSetUpMixin):
    def _get_student_list_data(self):
        request = self.factory.get("/homeworks/")
        request.user = self.student_user
        view = HomeworkListView()
        return view._get_view_data(self.student_user)

    def _get_teacher_list_data(self):
        request = self.factory.get("/homeworks/")
        request.user = self.teacher_user
        view = HomeworkListView()
        return view._get_view_data(self.teacher_user)

    def test_student_does_not_see_hidden_homework(self):
        data = self._get_student_list_data()
        titles = [hw.title for hw in data.homeworks]
        self.assertNotIn("Hidden", titles)

    def test_student_does_not_see_expired_homework(self):
        data = self._get_student_list_data()
        titles = [hw.title for hw in data.homeworks]
        self.assertNotIn("Expired", titles)

    def test_student_sees_visible_homework(self):
        data = self._get_student_list_data()
        titles = [hw.title for hw in data.homeworks]
        self.assertIn("Visible", titles)

    def test_teacher_sees_all_homeworks_including_hidden(self):
        data = self._get_teacher_list_data()
        titles = [hw.title for hw in data.homeworks]
        self.assertIn("Hidden", titles)

    def test_teacher_sees_all_homeworks_including_expired(self):
        data = self._get_teacher_list_data()
        titles = [hw.title for hw in data.homeworks]
        self.assertIn("Expired", titles)

    def test_teacher_list_item_exposes_is_hidden_flag(self):
        data = self._get_teacher_list_data()
        hidden_item = next(hw for hw in data.homeworks if hw.title == "Hidden")
        self.assertTrue(hidden_item.is_hidden)

    def test_teacher_list_item_exposes_is_accessible_to_students_false_for_hidden(self):
        data = self._get_teacher_list_data()
        hidden_item = next(hw for hw in data.homeworks if hw.title == "Hidden")
        self.assertFalse(hidden_item.is_accessible_to_students)

    def test_teacher_list_item_exposes_expires_at(self):
        data = self._get_teacher_list_data()
        expired_item = next(hw for hw in data.homeworks if hw.title == "Expired")
        self.assertIsNotNone(expired_item.expires_at)


# ─── HomeworkDetailView ───────────────────────────────────────────────────────


class HomeworkDetailViewExpiryTests(HomeworkExpiryViewSetUpMixin):
    def test_student_cannot_access_hidden_homework_detail(self):
        self.client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.hidden_hw.id})
        response = self.client.get(url)
        # Returns redirect (to list) when data is None
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_expired_homework_detail(self):
        self.client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.expired_hw.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_student_can_access_visible_homework_detail(self):
        self.client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.visible_hw.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_access_hidden_homework_detail(self):
        self.client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.hidden_hw.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_access_expired_homework_detail(self):
        self.client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.expired_hw.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_detail_data_includes_visibility_fields(self):
        self.client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.hidden_hw.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.context["data"]
        self.assertTrue(data.is_hidden)
        self.assertFalse(data.is_accessible_to_students)


# ─── SectionDetailView ────────────────────────────────────────────────────────


class SectionDetailViewExpiryTests(HomeworkExpiryViewSetUpMixin):
    def test_student_blocked_from_section_of_expired_homework(self):
        self.client.login(username="student", password="pass")
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.expired_hw.id,
                "section_id": self.expired_section.id,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_student_blocked_from_section_of_hidden_homework(self):
        # Add a section to hidden_hw
        hidden_section = Section.objects.create(
            homework=self.hidden_hw,
            title="Section 1",
            content="content",
            order=1,
        )
        self.client.login(username="student", password="pass")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.hidden_hw.id, "section_id": hidden_section.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_student_can_access_section_of_visible_homework(self):
        self.client.login(username="student", password="pass")
        url = reverse(
            "homeworks:section_detail",
            kwargs={"homework_id": self.visible_hw.id, "section_id": self.section.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_access_section_of_expired_homework(self):
        self.client.login(username="teacher", password="pass")
        url = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.expired_hw.id,
                "section_id": self.expired_section.id,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ─── Form validation ──────────────────────────────────────────────────────────


class HomeworkFormExpiryValidationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="t", password="p")
        self.teacher = Teacher.objects.create(user=user)
        self.course = Course.objects.create(name="C", code="C1")

    def _base_data(self, **overrides):
        data = {
            "title": "HW",
            "description": "desc",
            "course": self.course.id,
            "due_date": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
            "expires_at": (timezone.now() + timedelta(days=10)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "is_hidden": False,
        }
        data.update(overrides)
        return data

    def test_create_form_valid_when_expires_at_after_due_date(self):
        form = HomeworkCreateForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_warns_when_expires_at_before_due_date(self):
        """When expires_at < due_date, form is valid and expires_at_adjusted flag is set as warning."""
        due = timezone.now() + timedelta(days=3)
        data = self._base_data(
            due_date=due.strftime("%Y-%m-%dT%H:%M"),
            expires_at=(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        )
        form = HomeworkCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.expires_at_adjusted)

    def test_create_form_no_warning_when_expires_at_equals_due_date(self):
        """When expires_at == due_date, form is valid with no warning (equal is allowed)."""
        due = timezone.now() + timedelta(days=3)
        data = self._base_data(
            due_date=due.strftime("%Y-%m-%dT%H:%M"),
            expires_at=due.strftime("%Y-%m-%dT%H:%M"),
        )
        form = HomeworkCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.expires_at_adjusted)

    def test_create_form_valid_with_no_expires_at(self):
        data = self._base_data(expires_at="")
        form = HomeworkCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_form_valid_when_expires_at_after_due_date(self):
        hw = Homework.objects.create(
            title="HW",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )
        form = HomeworkEditForm(data=self._base_data(), instance=hw)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_form_warns_when_expires_at_before_due_date(self):
        """When expires_at < due_date, edit form is valid and expires_at_adjusted warning is set."""
        hw = Homework.objects.create(
            title="HW",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )
        data = self._base_data(
            expires_at=(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        )
        form = HomeworkEditForm(data=data, instance=hw)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.expires_at_adjusted)

    def test_edit_form_allows_past_due_date(self):
        """Edit form accepts any due_date — no restriction."""
        hw = Homework.objects.create(
            title="HW",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )
        data = self._base_data(
            due_date=(timezone.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
            expires_at="",
        )
        form = HomeworkEditForm(data=data, instance=hw)
        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_allows_today_as_due_date(self):
        """Create form allows due_date set to today."""
        data = self._base_data(
            due_date=timezone.now().strftime("%Y-%m-%dT%H:%M"),
        )
        form = HomeworkCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_rejects_past_due_date(self):
        """Create form rejects a due_date strictly in the past (yesterday)."""
        data = self._base_data(
            due_date=(timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        )
        form = HomeworkCreateForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)
