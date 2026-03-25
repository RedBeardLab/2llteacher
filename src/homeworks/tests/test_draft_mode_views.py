"""
Tests for draft mode enforcement in views.

Covers:
- Students cannot see draft homeworks in list or detail
- Teachers always see draft homeworks
- publish_now action publishes a draft
- auto_publish_due_drafts fires on list/detail page load
- Scheduled draft stays hidden before publish_at
"""

from datetime import timedelta

from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Teacher, Student
from courses.models import Course, CourseEnrollment, CourseTeacher
from homeworks.models import Homework, HomeworkType, Section

User = get_user_model()


class DraftModeViewSetUpMixin(TestCase):
    """Shared setUp for draft mode view tests."""

    def setUp(self):
        self.factory = RequestFactory()

        teacher_user = User.objects.create_user(
            username="teacher", email="t@test.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=teacher_user)
        self.teacher_user = teacher_user

        student_user = User.objects.create_user(
            username="student", email="s@test.com", password="pass"
        )
        self.student = Student.objects.create(user=student_user)
        self.student_user = student_user

        self.course = Course.objects.create(name="Course", code="C1", is_active=True)
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.published_hw = Homework.objects.create(
            title="Published",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.PUBLISHED,
            is_hidden=False,
        )

        self.draft_hw = Homework.objects.create(
            title="Draft",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
        )
        # Add a section so detail view can render
        Section.objects.create(
            homework=self.draft_hw, title="S1", content="content", order=1
        )
        Section.objects.create(
            homework=self.published_hw, title="S1", content="content", order=1
        )


class HomeworkListDraftTests(DraftModeViewSetUpMixin):
    """HomeworkListView — draft visibility."""

    def test_student_cannot_see_draft_in_list(self):
        client = Client()
        client.login(username="student", password="pass")
        response = client.get(reverse("homeworks:list"))
        titles = [hw.title for hw in response.context["data"].homeworks]
        self.assertNotIn("Draft", titles)
        self.assertIn("Published", titles)

    def test_teacher_sees_draft_in_list(self):
        client = Client()
        client.login(username="teacher", password="pass")
        response = client.get(reverse("homeworks:list"))
        titles = [hw.title for hw in response.context["data"].homeworks]
        self.assertIn("Draft", titles)
        self.assertIn("Published", titles)

    def test_teacher_list_item_has_is_draft_true(self):
        client = Client()
        client.login(username="teacher", password="pass")
        response = client.get(reverse("homeworks:list"))
        draft_items = [
            hw for hw in response.context["data"].homeworks if hw.title == "Draft"
        ]
        self.assertEqual(len(draft_items), 1)
        self.assertTrue(draft_items[0].is_draft)


class HomeworkDetailDraftTests(DraftModeViewSetUpMixin):
    """HomeworkDetailView — draft visibility."""

    def test_student_cannot_access_draft_detail(self):
        client = Client()
        client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.get(url)
        # Returns redirect (302) because _get_view_data returns None for inaccessible
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_access_draft_detail(self):
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail_data_has_is_draft_true_for_teacher(self):
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.get(url)
        self.assertTrue(response.context["data"].is_draft)


class PublishNowActionTests(DraftModeViewSetUpMixin):
    """HomeworkDetailView publish_now POST action."""

    def test_publish_now_publishes_draft(self):
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.post(url, {"action": "publish_now"})
        self.assertEqual(response.status_code, 302)
        self.draft_hw.refresh_from_db()
        self.assertFalse(self.draft_hw.is_hidden)
        self.assertEqual(self.draft_hw.homework_type, HomeworkType.PUBLISHED)
        self.assertIsNone(self.draft_hw.publish_at)

    def test_publish_now_forbidden_for_student(self):
        client = Client()
        client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.post(url, {"action": "publish_now"})
        self.assertEqual(response.status_code, 403)

    def test_publish_now_on_another_teachers_homework_is_forbidden(self):
        other_user = User.objects.create_user(username="other", password="pass")
        other_teacher = Teacher.objects.create(user=other_user)
        other_course = Course.objects.create(name="Other", code="OTH")
        other_hw = Homework.objects.create(
            title="Other Draft",
            description="desc",
            created_by=other_teacher,
            course=other_course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
        )
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": other_hw.id})
        response = client.post(url, {"action": "publish_now"})
        self.assertEqual(response.status_code, 403)


class DraftSaveMinimalDataTests(DraftModeViewSetUpMixin):
    """Draft saves with minimal data redirect instead of re-rendering."""

    def test_create_draft_with_only_title_redirects(self):
        """Saving a draft with just a title should succeed and redirect."""
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("courses:homework-create", kwargs={"course_id": self.course.id})
        response = client.post(
            url,
            {
                "save_draft": "1",
                "title": "Untitled Draft",
                "description": "",
                "due_date": "",
                "expires_at": "",
                "is_hidden": "",
                "publish_at": "",
                "llm_config": "",
                "sections-TOTAL_FORMS": "0",
                "sections-INITIAL_FORMS": "0",
                "sections-MIN_NUM_FORMS": "0",
                "sections-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)
        from homeworks.models import HomeworkType

        hw = Homework.objects.filter(title="Untitled Draft").first()
        self.assertIsNotNone(hw)
        self.assertEqual(hw.homework_type, HomeworkType.DRAFT)
        self.assertTrue(hw.is_hidden)
        self.assertIsNone(hw.due_date)

    def test_edit_draft_save_redirects_to_detail(self):
        """Saving draft on edit redirects to detail page, not the form."""
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.draft_hw.id})
        response = client.post(
            url,
            {
                "save_draft": "1",
                "title": "Updated Draft Title",
                "description": "",
                "due_date": "",
                "expires_at": "",
                "is_hidden": "",
                "publish_at": "",
                "llm_config": "",
                "sections-TOTAL_FORMS": "0",
                "sections-INITIAL_FORMS": "0",
                "sections-MIN_NUM_FORMS": "0",
                "sections-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.draft_hw.id), response["Location"])


class AutoPublishOnPageLoadTests(DraftModeViewSetUpMixin):
    """Auto-publish fires when list/detail loads."""

    def _make_scheduled_draft(self):
        hw = Homework.objects.create(
            title="Scheduled",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
            publish_at=timezone.now() - timedelta(seconds=1),
        )
        Section.objects.create(homework=hw, title="S1", content="content", order=1)
        return hw

    def test_auto_publish_fires_on_list_view_load(self):
        hw = self._make_scheduled_draft()
        client = Client()
        client.login(username="teacher", password="pass")
        client.get(reverse("homeworks:list"))
        hw.refresh_from_db()
        self.assertEqual(hw.homework_type, HomeworkType.PUBLISHED)
        self.assertFalse(hw.is_hidden)

    def test_auto_publish_fires_on_detail_view_load(self):
        hw = self._make_scheduled_draft()
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": hw.id})
        client.get(url)
        hw.refresh_from_db()
        self.assertEqual(hw.homework_type, HomeworkType.PUBLISHED)
        self.assertFalse(hw.is_hidden)

    def test_scheduled_draft_stays_hidden_before_publish_at(self):
        hw = Homework.objects.create(
            title="Future",
            description="desc",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
            publish_at=timezone.now() + timedelta(hours=2),
        )
        client = Client()
        client.login(username="student", password="pass")
        client.get(reverse("homeworks:list"))
        hw.refresh_from_db()
        self.assertEqual(hw.homework_type, HomeworkType.DRAFT)
        self.assertTrue(hw.is_hidden)


class HomeworkEditPublishTests(DraftModeViewSetUpMixin):
    """HomeworkEditView publish paths — publish_now and scheduled."""

    def _section_management(self):
        return {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            f"sections-0-id": str(Section.objects.filter(homework=self.published_hw).first().id),
            "sections-0-title": "Section 1",
            "sections-0-content": "Content",
            "sections-0-order": "1",
            "sections-0-solution": "",
        }

    def _publish_post(self, **overrides):
        base = {
            "publish": "1",
            "publish_now": "on",
            "title": self.published_hw.title,
            "description": self.published_hw.description,
            "due_date": (timezone.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
            "expires_at": "",
            "publish_at": "",
            "llm_config": "",
            **self._section_management(),
        }
        base.update(overrides)
        return base

    def test_publish_now_sets_published_and_not_hidden(self):
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.published_hw.id})
        response = client.post(url, self._publish_post())
        self.assertEqual(response.status_code, 302)
        self.published_hw.refresh_from_db()
        self.assertFalse(self.published_hw.is_hidden)
        self.assertEqual(self.published_hw.homework_type, HomeworkType.PUBLISHED)
        self.assertIsNone(self.published_hw.publish_at)

    def test_publish_now_clears_stale_expires_at(self):
        """Re-publishing an expired homework should clear expires_at."""
        self.published_hw.expires_at = timezone.now() - timedelta(days=1)
        self.published_hw.save()
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.published_hw.id})
        response = client.post(url, self._publish_post())
        self.assertEqual(response.status_code, 302)
        self.published_hw.refresh_from_db()
        self.assertIsNone(self.published_hw.expires_at)

    def test_publish_now_does_not_clear_future_expires_at(self):
        """A future expires_at submitted in the form is preserved when re-publishing."""
        future_expires = timezone.now() + timedelta(days=30)
        self.published_hw.expires_at = future_expires
        self.published_hw.save()
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.published_hw.id})
        # Explicitly include expires_at in POST to preserve it
        post = self._publish_post(expires_at=future_expires.strftime("%Y-%m-%dT%H:%M"))
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        self.published_hw.refresh_from_db()
        self.assertIsNotNone(self.published_hw.expires_at)

    def test_scheduled_publish_keeps_homework_as_draft(self):
        """Clicking publish without publish_now + future publish_at → stays DRAFT."""
        future_publish = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        post = self._publish_post(publish_at=future_publish)
        del post["publish_now"]  # uncheck the toggle
        client = Client()
        client.login(username="teacher", password="pass")
        url = reverse("homeworks:edit", kwargs={"homework_id": self.draft_hw.id})
        # Need draft hw's section
        section = Section.objects.filter(homework=self.draft_hw).first()
        post["sections-0-id"] = str(section.id)
        post["sections-0-title"] = "S1"
        post["sections-0-content"] = "content"
        post["sections-0-order"] = "1"
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        self.draft_hw.refresh_from_db()
        self.assertEqual(self.draft_hw.homework_type, HomeworkType.DRAFT)
        self.assertTrue(self.draft_hw.is_hidden)
        self.assertIsNotNone(self.draft_hw.publish_at)

    def test_scheduled_draft_not_visible_to_students(self):
        """A scheduled draft (future publish_at) remains invisible to students."""
        self.draft_hw.publish_at = timezone.now() + timedelta(hours=2)
        self.draft_hw.save()
        client = Client()
        client.login(username="student", password="pass")
        url = reverse("homeworks:detail", kwargs={"homework_id": self.draft_hw.id})
        response = client.get(url)
        self.assertEqual(response.status_code, 302)  # inaccessible → redirect


class AutoPublishServiceTests(DraftModeViewSetUpMixin):
    """HomeworkService.auto_publish_due_drafts edge cases."""

    def test_returns_count_of_published_homeworks(self):
        from homeworks.services import HomeworkService
        # Create 2 more overdue drafts
        for i in range(2):
            Homework.objects.create(
                title=f"Scheduled {i}",
                description="",
                created_by=self.teacher,
                course=self.course,
                due_date=timezone.now() + timedelta(days=7),
                homework_type=HomeworkType.DRAFT,
                is_hidden=True,
                publish_at=timezone.now() - timedelta(seconds=1),
            )
        count = HomeworkService.auto_publish_due_drafts()
        self.assertEqual(count, 2)

    def test_does_not_touch_published_homeworks(self):
        from homeworks.services import HomeworkService
        HomeworkService.auto_publish_due_drafts()
        self.published_hw.refresh_from_db()
        self.assertFalse(self.published_hw.is_hidden)
        self.assertEqual(self.published_hw.homework_type, HomeworkType.PUBLISHED)

    def test_does_not_touch_drafts_with_future_publish_at(self):
        from homeworks.services import HomeworkService
        future_draft = Homework.objects.create(
            title="Future Draft",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.DRAFT,
            is_hidden=True,
            publish_at=timezone.now() + timedelta(hours=2),
        )
        HomeworkService.auto_publish_due_drafts()
        future_draft.refresh_from_db()
        self.assertEqual(future_draft.homework_type, HomeworkType.DRAFT)
        self.assertTrue(future_draft.is_hidden)

    def test_does_not_touch_hidden_type_homeworks(self):
        """HIDDEN type (manually hidden, not draft) should not be auto-published."""
        from homeworks.services import HomeworkService
        hidden_hw = Homework.objects.create(
            title="Hidden",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
            homework_type=HomeworkType.HIDDEN,
            is_hidden=True,
            publish_at=timezone.now() - timedelta(seconds=1),
        )
        HomeworkService.auto_publish_due_drafts()
        hidden_hw.refresh_from_db()
        self.assertEqual(hidden_hw.homework_type, HomeworkType.HIDDEN)

    def test_publish_homework_idempotent(self):
        """Calling publish_homework on an already-published homework is safe."""
        from homeworks.services import HomeworkService
        result = HomeworkService.publish_homework(self.published_hw.id)
        self.assertTrue(result.success)
        self.published_hw.refresh_from_db()
        self.assertFalse(self.published_hw.is_hidden)
        self.assertEqual(self.published_hw.homework_type, HomeworkType.PUBLISHED)
