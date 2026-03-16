"""
Tests for the Homework expiry and visibility model properties.

Covers:
- is_expired property
- is_accessible_to_students property
- Default field values
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Teacher
from courses.models import Course
from django.contrib.auth import get_user_model
from homeworks.models import Homework

User = get_user_model()


class HomeworkExpiryModelTests(TestCase):
    """Tests for Homework.is_expired and is_accessible_to_students."""

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
        data = {**self.base_data, **kwargs}
        return Homework.objects.create(**data)

    # --- defaults ---

    def test_expires_at_defaults_to_null(self):
        hw = self._make()
        self.assertIsNone(hw.expires_at)

    def test_is_hidden_defaults_to_false(self):
        hw = self._make()
        self.assertFalse(hw.is_hidden)

    # --- is_expired ---

    def test_is_expired_false_when_expires_at_is_null(self):
        hw = self._make()
        self.assertFalse(hw.is_expired)

    def test_is_expired_false_when_expires_at_is_in_future(self):
        hw = self._make(expires_at=timezone.now() + timedelta(days=3))
        self.assertFalse(hw.is_expired)

    def test_is_expired_true_when_expires_at_is_in_past(self):
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

    def test_accessible_when_not_hidden_and_future_expiry(self):
        hw = self._make(
            is_hidden=False,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertTrue(hw.is_accessible_to_students)

    def test_not_accessible_when_hidden_despite_future_expiry(self):
        hw = self._make(
            is_hidden=True,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(hw.is_accessible_to_students)
