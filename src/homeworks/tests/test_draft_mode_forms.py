"""
Tests for draft mode form validation.

Covers:
- HomeworkCreateForm: publish_at validation (past rejected, future accepted, publish_now bypasses)
- HomeworkCreateForm: due_date validation (today allowed, past rejected)
- HomeworkEditForm: publish_at not restricted on edit; requires when publishing scheduled
- SectionFormSet: section presence and draft bypass; section order normalization
"""

from datetime import timedelta

from django.forms import formset_factory
from django.test import TestCase
from django.utils import timezone

from accounts.models import Teacher
from courses.models import Course
from django.contrib.auth import get_user_model
from homeworks.forms import (
    HomeworkCreateForm,
    HomeworkEditForm,
    SectionForm,
    SectionFormSet,
    normalize_section_formset_orders,
)
from homeworks.models import Homework, HomeworkType

User = get_user_model()


def _make_section_post(sections, prefix="sections"):
    """Build a POST dict for a SectionFormSet from a list of dicts."""
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(sections)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, s in enumerate(sections):
        data[f"{prefix}-{i}-id"] = s.get("id", "")
        data[f"{prefix}-{i}-title"] = s.get("title", "")
        data[f"{prefix}-{i}-content"] = s.get("content", "")
        data[f"{prefix}-{i}-order"] = str(s.get("order", i + 1))
        data[f"{prefix}-{i}-solution"] = s.get("solution", "")
        data[f"{prefix}-{i}-section_type"] = s.get("section_type", "conversation")
        if s.get("DELETE"):
            data[f"{prefix}-{i}-DELETE"] = "on"
    return data


def _make_formset(sections, is_draft=False):
    FS = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
    post = _make_section_post(sections)
    fs = FS(post, prefix="sections")
    fs.is_draft_save = is_draft
    return fs


class DraftModeFormSetUpMixin(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="teacher", password="pass")
        self.teacher = Teacher.objects.create(user=user)
        self.course = Course.objects.create(name="Course", code="C1")
        self.future = timezone.now() + timedelta(days=7)
        self.base_post = {
            "title": "HW",
            "description": "desc",
            "course": str(self.course.id),
            "due_date": self.future.strftime("%Y-%m-%dT%H:%M"),
            "expires_at": "",
            "publish_at": "",
            "llm_config": "",
        }


# ---------------------------------------------------------------------------
# HomeworkCreateForm
# ---------------------------------------------------------------------------

class HomeworkCreateFormPublishAtTests(DraftModeFormSetUpMixin):
    def test_valid_with_no_publish_at_and_no_submit_button(self):
        """No publish button in POST — publish_at is optional."""
        form = HomeworkCreateForm(self.base_post)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_publish_now_checked_and_no_publish_at(self):
        """publish_now in POST → schedule validation skipped even if publish_at empty."""
        data = {**self.base_post, "publish": "1", "publish_now": "on"}
        form = HomeworkCreateForm(data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_when_scheduling_without_publish_at(self):
        """publish button + no publish_now + no publish_at → required error."""
        data = {**self.base_post, "publish": "1"}
        form = HomeworkCreateForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("publish_at", form.errors)

    def test_valid_with_future_publish_at_when_scheduling(self):
        data = {
            **self.base_post,
            "publish": "1",
            "publish_at": (timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
        }
        form = HomeworkCreateForm(data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_with_past_publish_at(self):
        data = {
            **self.base_post,
            "publish_at": (timezone.localtime(timezone.now()) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        }
        form = HomeworkCreateForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("publish_at", form.errors)


class HomeworkCreateFormDueDateTests(DraftModeFormSetUpMixin):
    def test_due_date_today_is_valid(self):
        """Today's date is allowed — only strictly past dates are rejected."""
        today_end = timezone.now().replace(hour=23, minute=59, second=0, microsecond=0)
        data = {**self.base_post, "due_date": today_end.strftime("%Y-%m-%dT%H:%M")}
        form = HomeworkCreateForm(data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_due_date_yesterday_is_invalid(self):
        yesterday = timezone.localtime(timezone.now()) - timedelta(days=1)
        data = {**self.base_post, "due_date": yesterday.strftime("%Y-%m-%dT%H:%M")}
        form = HomeworkCreateForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)

    def test_publish_requires_due_date(self):
        data = {**self.base_post, "due_date": ""}
        form = HomeworkCreateForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)

    def test_description_optional_when_is_draft_save(self):
        """is_draft_save=True makes description optional."""
        data = {**self.base_post, "description": ""}
        form = HomeworkCreateForm(data, is_draft_save=True)
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# HomeworkEditForm
# ---------------------------------------------------------------------------

class HomeworkEditFormTests(DraftModeFormSetUpMixin):
    def setUp(self):
        super().setUp()
        self.homework = Homework.objects.create(
            title="HW",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=self.future,
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
            publish_at=timezone.now() + timedelta(days=2),
        )

    def _post(self, **overrides):
        base = {
            "title": "HW",
            "description": "desc",
            "due_date": self.future.strftime("%Y-%m-%dT%H:%M"),
            "expires_at": "",
            "publish_at": "",
            "llm_config": "",
        }
        base.update(overrides)
        return base

    def test_valid_with_no_publish_at(self):
        form = HomeworkEditForm(self._post(), instance=self.homework)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_past_publish_at(self):
        """Edit form allows past publish_at — teacher may be correcting a mistake."""
        past = (timezone.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        form = HomeworkEditForm(self._post(publish_at=past), instance=self.homework)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_future_publish_at(self):
        future = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        form = HomeworkEditForm(self._post(publish_at=future), instance=self.homework)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_when_scheduling_without_publish_at(self):
        """publish button + no publish_now + no publish_at → required error on edit too."""
        data = {**self._post(), "publish": "1"}
        form = HomeworkEditForm(data, instance=self.homework)
        self.assertFalse(form.is_valid())
        self.assertIn("publish_at", form.errors)

    def test_valid_when_publish_now_checked_and_no_publish_at(self):
        data = {**self._post(), "publish": "1", "publish_now": "on"}
        form = HomeworkEditForm(data, instance=self.homework)
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# SectionFormSet
# ---------------------------------------------------------------------------

class SectionFormSetOrderTests(TestCase):
    def _section(self, order, title="T", content="C"):
        return {"title": title, "content": content, "order": order}

    def test_valid_sequential_sections(self):
        fs = _make_formset([self._section(1), self._section(2), self._section(3)])
        self.assertTrue(fs.is_valid(), fs.errors)

    def test_duplicate_order_is_allowed_and_normalized(self):
        fs = _make_formset([self._section(1), self._section(1)])
        self.assertTrue(fs.is_valid(), fs.errors)
        forms = normalize_section_formset_orders(fs)
        self.assertEqual([form.cleaned_data["order"] for form in forms], [1, 2])

    def test_gap_in_order_is_allowed_and_normalized(self):
        fs = _make_formset([self._section(1), self._section(3)])
        self.assertTrue(fs.is_valid(), fs.errors)
        forms = normalize_section_formset_orders(fs)
        self.assertEqual([form.cleaned_data["order"] for form in forms], [1, 2])

    def test_order_not_starting_at_1_is_allowed_and_normalized(self):
        fs = _make_formset([self._section(2), self._section(3)])
        self.assertTrue(fs.is_valid(), fs.errors)
        forms = normalize_section_formset_orders(fs)
        self.assertEqual([form.cleaned_data["order"] for form in forms], [1, 2])

    def test_blank_order_is_allowed_and_normalized(self):
        fs = _make_formset([self._section(""), self._section("")])
        self.assertTrue(fs.is_valid(), fs.errors)
        forms = normalize_section_formset_orders(fs)
        self.assertEqual([form.cleaned_data["order"] for form in forms], [1, 2])

    def test_malformed_order_is_allowed_and_normalized(self):
        fs = _make_formset([self._section("__NUM__"), self._section("not-an-int")])
        self.assertTrue(fs.is_valid(), fs.errors)
        forms = normalize_section_formset_orders(fs)
        self.assertEqual([form.cleaned_data["order"] for form in forms], [1, 2])

    def test_empty_formset_rejected_for_publish(self):
        FS = formset_factory(SectionForm, extra=0, formset=SectionFormSet)
        post = _make_section_post([])
        fs = FS(post, prefix="sections")
        fs.is_draft_save = False
        self.assertFalse(fs.is_valid())
        self.assertTrue(any("required" in str(e) for e in fs.non_form_errors()))

    def test_empty_formset_valid_for_draft_save(self):
        fs = _make_formset([], is_draft=True)
        self.assertTrue(fs.is_valid(), fs.errors)

    def test_single_valid_section_passes(self):
        fs = _make_formset([{"title": "T", "content": "C", "order": 1}])
        self.assertTrue(fs.is_valid(), fs.errors)
