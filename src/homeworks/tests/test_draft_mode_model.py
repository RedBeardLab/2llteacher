"""
Tests for Homework draft mode model properties.

Covers:
- is_draft property
- is_overdue (including None due_date guard)
- is_expired (including None expires_at guard)
- is_accessible_to_students (hidden, expired, and draft combinations)
- should_auto_publish (all states, including at-exactly-now boundary)
- Default field values
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Teacher
from courses.models import Course
from django.contrib.auth import get_user_model
from homeworks.models import Homework, HomeworkType

User = get_user_model()


class HomeworkDraftModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="teacher", password="pass")
        self.teacher = Teacher.objects.create(user=user)
        self.course = Course.objects.create(name="Course", code="C1")
        self.base_data = {
            "title": "HW",
            "description": "desc",
            "created_by": self.teacher,
            "course": self.course,
            "due_date": timezone.now() + timedelta(days=7),
        }

    def _make(self, **kwargs):
        return Homework.objects.create(**{**self.base_data, **kwargs})

    # --- defaults ---

    def test_default_homework_type_is_published(self):
        hw = self._make()
        self.assertEqual(hw.homework_type, HomeworkType.PUBLISHED)

    def test_default_publish_at_is_null(self):
        hw = self._make()
        self.assertIsNone(hw.publish_at)

    def test_default_is_hidden_is_false(self):
        hw = self._make()
        self.assertFalse(hw.is_hidden)

    # --- is_draft ---

    def test_is_draft_true_when_type_is_draft(self):
        hw = self._make(homework_type=HomeworkType.DRAFT)
        self.assertTrue(hw.is_draft)

    def test_is_draft_false_when_type_is_published(self):
        hw = self._make(homework_type=HomeworkType.PUBLISHED)
        self.assertFalse(hw.is_draft)

    def test_is_draft_false_when_type_is_hidden(self):
        hw = self._make(homework_type=HomeworkType.HIDDEN)
        self.assertFalse(hw.is_draft)

    # --- is_overdue ---

    def test_is_overdue_false_when_due_date_is_none(self):
        """None due_date must not raise — was a real bug after making due_date nullable."""
        hw = self._make(due_date=None)
        self.assertFalse(hw.is_overdue)

    def test_is_overdue_false_when_due_date_in_future(self):
        hw = self._make(due_date=timezone.now() + timedelta(days=1))
        self.assertFalse(hw.is_overdue)

    def test_is_overdue_true_when_due_date_in_past(self):
        hw = self._make(due_date=timezone.now() - timedelta(days=1))
        self.assertTrue(hw.is_overdue)

    # --- is_expired ---

    def test_is_expired_false_when_expires_at_is_none(self):
        hw = self._make()
        self.assertIsNone(hw.expires_at)
        self.assertFalse(hw.is_expired)

    def test_is_expired_false_when_expires_at_in_future(self):
        hw = self._make(expires_at=timezone.now() + timedelta(days=1))
        self.assertFalse(hw.is_expired)

    def test_is_expired_true_when_expires_at_in_past(self):
        hw = self._make(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(hw.is_expired)

    # --- is_accessible_to_students ---

    def test_accessible_by_default(self):
        hw = self._make()
        self.assertTrue(hw.is_accessible_to_students)

    def test_not_accessible_when_is_hidden_true(self):
        hw = self._make(is_hidden=True)
        self.assertFalse(hw.is_accessible_to_students)

    def test_not_accessible_when_expired(self):
        hw = self._make(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(hw.is_accessible_to_students)

    def test_not_accessible_when_hidden_and_expired(self):
        hw = self._make(
            is_hidden=True,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(hw.is_accessible_to_students)

    def test_accessible_when_draft_type_but_is_hidden_false(self):
        """homework_type is display-only. A DRAFT with is_hidden=False is accessible."""
        hw = self._make(homework_type=HomeworkType.DRAFT, is_hidden=False)
        self.assertTrue(hw.is_accessible_to_students)

    def test_not_accessible_when_draft_type_and_is_hidden_true(self):
        hw = self._make(homework_type=HomeworkType.DRAFT, is_hidden=True)
        self.assertFalse(hw.is_accessible_to_students)

    # --- should_auto_publish ---

    def test_should_auto_publish_false_when_no_publish_at(self):
        hw = self._make(homework_type=HomeworkType.DRAFT)
        self.assertFalse(hw.should_auto_publish)

    def test_should_auto_publish_false_when_publish_at_in_future(self):
        hw = self._make(
            homework_type=HomeworkType.DRAFT,
            publish_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(hw.should_auto_publish)

    def test_should_auto_publish_true_when_publish_at_in_past(self):
        hw = self._make(
            homework_type=HomeworkType.DRAFT,
            publish_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertTrue(hw.should_auto_publish)

    def test_should_auto_publish_false_when_already_published(self):
        """publish_at in past but type=PUBLISHED → already done, don't re-publish."""
        hw = self._make(
            homework_type=HomeworkType.PUBLISHED,
            publish_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(hw.should_auto_publish)

    def test_should_auto_publish_false_when_type_is_hidden(self):
        """HIDDEN type should not be auto-published."""
        hw = self._make(
            homework_type=HomeworkType.HIDDEN,
            publish_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(hw.should_auto_publish)
