"""
Tests for HomeworkProgressWidget model and related functionality.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import IntegrityError
import uuid

from homeworks.models import Homework, HomeworkProgressWidget
from accounts.models import Teacher
from courses.models import Course


class HomeworkProgressWidgetModelTest(TestCase):
    """Test cases for the HomeworkProgressWidget model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now(),
        )

    def test_widget_creation(self):
        """Test basic widget creation."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="How much do you know about this topic?",
            post_prompt="How much do you now know about this topic?",
            order=1,
        )
        self.assertEqual(widget.homework, self.homework)
        self.assertEqual(widget.pre_prompt, "How much do you know about this topic?")
        self.assertEqual(widget.post_prompt, "How much do you now know about this topic?")
        self.assertEqual(widget.order, 1)
        self.assertIsInstance(widget.id, uuid.UUID)

    def test_widget_uuid_primary_key(self):
        """Test that widget has UUID primary key."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="Post prompt",
            order=1,
        )
        self.assertIsInstance(widget.id, uuid.UUID)

    def test_widget_timestamps(self):
        """Test widget timestamp fields."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="Post prompt",
            order=1,
        )
        self.assertIsNotNone(widget.created_at)
        self.assertIsNotNone(widget.updated_at)

    def test_widget_str_representation(self):
        """Test widget string representation."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="Post prompt",
            order=1,
        )
        self.assertIn("1", str(widget))
        self.assertIn(self.homework.title, str(widget))

    def test_widget_ordering(self):
        """Test widget ordering by order field."""
        widget1 = HomeworkProgressWidget.objects.create(
            homework=self.homework, pre_prompt="Pre 1", post_prompt="Post 1", order=2
        )
        widget2 = HomeworkProgressWidget.objects.create(
            homework=self.homework, pre_prompt="Pre 2", post_prompt="Post 2", order=1
        )
        widget3 = HomeworkProgressWidget.objects.create(
            homework=self.homework, pre_prompt="Pre 3", post_prompt="Post 3", order=3
        )

        widgets = list(HomeworkProgressWidget.objects.filter(homework=self.homework))
        self.assertEqual(widgets[0].order, 1)
        self.assertEqual(widgets[1].order, 2)
        self.assertEqual(widgets[2].order, 3)

    def test_widget_unique_order_per_homework(self):
        """Test that order must be unique per homework."""
        HomeworkProgressWidget.objects.create(
            homework=self.homework, pre_prompt="Pre 1", post_prompt="Post 1", order=1
        )
        with self.assertRaises(IntegrityError):
            HomeworkProgressWidget.objects.create(
                homework=self.homework,
                pre_prompt="Pre 2",
                post_prompt="Post 2",
                order=1,
            )

    def test_multiple_widgets_different_homeworks_same_order(self):
        """Test that same order is allowed for different homeworks."""
        homework2 = Homework.objects.create(
            title="Test Homework 2",
            description="Test homework 2",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now(),
        )
        HomeworkProgressWidget.objects.create(
            homework=self.homework, pre_prompt="Pre 1", post_prompt="Post 1", order=1
        )
        widget2 = HomeworkProgressWidget.objects.create(
            homework=homework2, pre_prompt="Pre 1", post_prompt="Post 1", order=1
        )
        self.assertEqual(widget2.order, 1)

    def test_widget_order_required(self):
        """Test that order is required."""
        with self.assertRaises(IntegrityError):
            HomeworkProgressWidget.objects.create(
                homework=self.homework,
                pre_prompt="Pre prompt",
                post_prompt="Post prompt",
            )

    def test_widget_homework_relationship(self):
        """Test the homework relationship."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="Post prompt",
            order=1,
        )
        self.assertEqual(self.homework.progress_widgets.count(), 1)
        self.assertEqual(self.homework.progress_widgets.first(), widget)

    def test_widget_with_empty_post_prompt(self):
        """Test widget creation with empty post_prompt (allowed)."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="",
            order=1,
        )
        self.assertEqual(widget.post_prompt, "")

    def test_widget_order_min_max_validation(self):
        """Test order field min/max validation through model."""
        widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt",
            post_prompt="Post prompt",
            order=20,
        )
        self.assertEqual(widget.order, 20)

        widget2 = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt 2",
            post_prompt="Post prompt 2",
            order=1,
        )
        self.assertEqual(widget2.order, 1)


class HomeworkProgressWidgetResponseModelTest(TestCase):
    """Test cases for the HomeworkProgressWidgetResponse model."""

    def setUp(self):
        from conversations.models import HomeworkProgressWidgetResponse

        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )
        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now(),
        )
        self.widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="How much do you know about this topic?",
            post_prompt="How much do you now know about this topic?",
            order=1,
        )
        self.WidgetResponse = HomeworkProgressWidgetResponse

    def test_response_creation(self):
        """Test basic response creation."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        self.assertEqual(response.user, self.user)
        self.assertEqual(response.widget, self.widget)
        self.assertEqual(response.pre_value, 5)
        self.assertIsNone(response.post_value)

    def test_response_with_post_value(self):
        """Test response with both pre and post values."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5, post_value=8
        )
        self.assertEqual(response.pre_value, 5)
        self.assertEqual(response.post_value, 8)

    def test_response_unique_user_widget(self):
        """Test that user+widget combination must be unique."""
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        with self.assertRaises(IntegrityError):
            self.WidgetResponse.objects.create(
                user=self.user, widget=self.widget, pre_value=7
            )

    def test_response_different_users_same_widget(self):
        """Test that different users can have responses for the same widget."""
        user2 = self.User.objects.create_user(username="student2", password="pass123")
        response1 = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        response2 = self.WidgetResponse.objects.create(
            user=user2, widget=self.widget, pre_value=7
        )
        self.assertEqual(response1.pre_value, 5)
        self.assertEqual(response2.pre_value, 7)

    def test_response_value_range(self):
        """Test response value range validation."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=10
        )
        self.assertEqual(response.pre_value, 10)

        user2 = self.User.objects.create_user(username="student_range", password="pass123")
        response2 = self.WidgetResponse.objects.create(
            user=user2,
            widget=self.widget,
            pre_value=0,
            post_value=0,
        )
        self.assertEqual(response2.pre_value, 0)
        self.assertEqual(response2.post_value, 0)

    def test_response_timestamps(self):
        """Test response timestamp fields."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        self.assertIsNotNone(response.pre_submitted_at)
        self.assertIsNone(response.post_submitted_at)

    def test_response_update_post_value(self):
        """Test updating post value."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        response.post_value = 8
        response.save()

        updated = self.WidgetResponse.objects.get(id=response.id)
        self.assertEqual(updated.pre_value, 5)
        self.assertEqual(updated.post_value, 8)
        self.assertIsNotNone(updated.post_submitted_at)

    def test_response_widget_relationship(self):
        """Test widget responses relationship."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        self.assertEqual(self.widget.responses.count(), 1)
        self.assertEqual(self.widget.responses.first(), response)

    def test_response_user_relationship(self):
        """Test user responses relationship."""
        response = self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget, pre_value=5
        )
        self.assertEqual(self.user.widget_responses.count(), 1)
        self.assertEqual(self.user.widget_responses.first(), response)


class ProgressWidgetFormTest(TestCase):
    """Test cases for ProgressWidgetForm."""

    def test_form_creation(self):
        """Test basic form creation."""
        from homeworks.forms import ProgressWidgetForm

        form = ProgressWidgetForm(
            {
                "pre_prompt": "How much do you know?",
                "post_prompt": "How much do you now know?",
                "order": "1",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["pre_prompt"], "How much do you know?")
        self.assertEqual(form.cleaned_data["post_prompt"], "How much do you now know?")
        self.assertEqual(form.cleaned_data["order"], "1")

    def test_form_with_id(self):
        """Test form with existing widget ID."""
        from homeworks.forms import ProgressWidgetForm
        from uuid import UUID

        widget_id = "12345678-1234-1234-1234-123456789012"
        form = ProgressWidgetForm(
            {
                "id": widget_id,
                "pre_prompt": "Pre prompt",
                "post_prompt": "Post prompt",
                "order": "1",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(str(form.cleaned_data["id"]), widget_id)

    def test_form_missing_pre_prompt(self):
        """Test form validation fails without pre_prompt."""
        from homeworks.forms import ProgressWidgetForm

        form = ProgressWidgetForm(
            {
                "post_prompt": "Post prompt",
                "order": "1",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pre_prompt", form.errors)

    def test_form_missing_post_prompt(self):
        """Test form is valid without post_prompt (pre only widget)."""
        from homeworks.forms import ProgressWidgetForm

        form = ProgressWidgetForm(
            {
                "pre_prompt": "Pre prompt",
                "order": "1",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["post_prompt"], "")

    def test_form_delete_field(self):
        """Test form has DELETE field for formset."""
        from homeworks.forms import ProgressWidgetForm

        form = ProgressWidgetForm(
            {
                "pre_prompt": "Pre prompt",
                "post_prompt": "Post prompt",
                "order": "1",
                "DELETE": "on",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data.get("DELETE", False))


class ProgressWidgetFormSetTest(TestCase):
    """Test cases for ProgressWidgetFormSet."""

    def test_formset_creation(self):
        """Test basic formset creation."""
        from django.forms import formset_factory
        from homeworks.forms import ProgressWidgetForm, ProgressWidgetFormSet

        FS = formset_factory(ProgressWidgetForm, extra=0, formset=ProgressWidgetFormSet)
        post = {
            "widgets-TOTAL_FORMS": "2",
            "widgets-INITIAL_FORMS": "0",
            "widgets-MIN_NUM_FORMS": "0",
            "widgets-MAX_NUM_FORMS": "1000",
            "widgets-0-id": "",
            "widgets-0-pre_prompt": "Pre 1",
            "widgets-0-post_prompt": "Post 1",
            "widgets-0-order": "1",
            "widgets-1-id": "",
            "widgets-1-pre_prompt": "Pre 2",
            "widgets-1-post_prompt": "Post 2",
            "widgets-1-order": "2",
        }
        fs = FS(post, prefix="widgets")
        self.assertEqual(len(fs.forms), 2)
        self.assertTrue(fs.is_valid())

    def test_formset_with_delete(self):
        """Test formset with one widget marked for deletion."""
        from django.forms import formset_factory
        from homeworks.forms import ProgressWidgetForm, ProgressWidgetFormSet

        FS = formset_factory(ProgressWidgetForm, extra=0, formset=ProgressWidgetFormSet)
        post = {
            "widgets-TOTAL_FORMS": "2",
            "widgets-INITIAL_FORMS": "0",
            "widgets-MIN_NUM_FORMS": "0",
            "widgets-MAX_NUM_FORMS": "1000",
            "widgets-0-id": "",
            "widgets-0-pre_prompt": "Pre 1",
            "widgets-0-post_prompt": "Post 1",
            "widgets-0-order": "1",
            "widgets-1-id": "12345678-1234-1234-1234-123456789012",
            "widgets-1-pre_prompt": "Pre 2",
            "widgets-1-post_prompt": "Post 2",
            "widgets-1-order": "2",
            "widgets-1-DELETE": "on",
        }
        fs = FS(post, prefix="widgets")
        self.assertTrue(fs.is_valid())
        self.assertTrue(fs.forms[1].cleaned_data.get("DELETE", False))

    def test_normalize_widget_formset_orders(self):
        """Test order normalization for active widgets."""
        from django.forms import formset_factory
        from homeworks.forms import (
            ProgressWidgetForm,
            ProgressWidgetFormSet,
            normalize_progress_widget_formset_orders,
        )

        FS = formset_factory(ProgressWidgetForm, extra=0, formset=ProgressWidgetFormSet)
        post = {
            "widgets-TOTAL_FORMS": "3",
            "widgets-INITIAL_FORMS": "0",
            "widgets-MIN_NUM_FORMS": "0",
            "widgets-MAX_NUM_FORMS": "1000",
            "widgets-0-id": "",
            "widgets-0-pre_prompt": "Pre 3",
            "widgets-0-post_prompt": "Post 3",
            "widgets-0-order": "3",
            "widgets-1-id": "",
            "widgets-1-pre_prompt": "Pre 1",
            "widgets-1-post_prompt": "Post 1",
            "widgets-1-order": "1",
            "widgets-2-id": "",
            "widgets-2-pre_prompt": "Pre 2",
            "widgets-2-post_prompt": "Post 2",
            "widgets-2-order": "2",
        }
        fs = FS(post, prefix="widgets")
        fs.is_valid()
        active = normalize_progress_widget_formset_orders(fs)
        self.assertEqual(active[0].cleaned_data["order"], 1)
        self.assertEqual(active[1].cleaned_data["order"], 2)
        self.assertEqual(active[2].cleaned_data["order"], 3)


class HomeworkServiceWidgetMethodsTest(TestCase):
    """Test cases for HomeworkService widget-related methods."""

    def setUp(self):
        from courses.models import Course
        from conversations.models import HomeworkProgressWidgetResponse

        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )
        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now(),
        )
        self.widget1 = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="How much do you know about topic 1?",
            post_prompt="How much do you now know about topic 1?",
            order=1,
        )
        self.widget2 = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="How much do you know about topic 2?",
            post_prompt="How much do you now know about topic 2?",
            order=2,
        )
        self.WidgetResponse = HomeworkProgressWidgetResponse

    def test_can_access_sections_no_widgets(self):
        """Test that student can access sections when homework has no widgets."""
        from homeworks.services import HomeworkService
        from courses.models import Course

        new_course = Course.objects.create(name="Course 2", code="C2")
        homework_no_widgets = Homework.objects.create(
            title="HW No Widgets",
            description="Test",
            created_by=self.teacher,
            course=new_course,
            due_date=timezone.now(),
        )

        result = HomeworkService.can_access_sections(self.user, homework_no_widgets)
        self.assertTrue(result)

    def test_can_access_sections_all_pre_answered(self):
        """Test that student can access sections when all pre widgets answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5
        )
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget2, pre_value=7
        )
        result = HomeworkService.can_access_sections(self.user, self.homework)
        self.assertTrue(result)

    def test_can_access_sections_not_all_pre_answered(self):
        """Test that student cannot access sections when not all pre widgets answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5
        )
        result = HomeworkService.can_access_sections(self.user, self.homework)
        self.assertFalse(result)

    def test_can_access_sections_no_responses(self):
        """Test that student cannot access sections when no widgets answered."""
        from homeworks.services import HomeworkService

        result = HomeworkService.can_access_sections(self.user, self.homework)
        self.assertFalse(result)

    def test_can_submit_homework_all_post_answered(self):
        """Test that student can submit when all post widgets answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5, post_value=8
        )
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget2, pre_value=7, post_value=9
        )
        result = HomeworkService.can_submit_homework(self.user, self.homework)
        self.assertTrue(result)

    def test_can_submit_homework_not_all_post_answered(self):
        """Test that student cannot submit when not all post widgets answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5, post_value=8
        )
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget2, pre_value=7
        )
        result = HomeworkService.can_submit_homework(self.user, self.homework)
        self.assertFalse(result)

    def test_get_next_unanswered_widget_pre_not_answered(self):
        """Test get next unanswered widget when pre is not answered."""
        from homeworks.services import HomeworkService

        widget = HomeworkService.get_next_unanswered_widget(self.user, self.homework)
        self.assertEqual(widget.id, self.widget1.id)
        self.assertEqual(widget.order, 1)
        self.assertIsNone(widget.pre_value)

    def test_get_next_unanswered_widget_all_answered(self):
        """Test get next unanswered widget when all are answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5, post_value=8
        )
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget2, pre_value=7, post_value=9
        )
        widget = HomeworkService.get_next_unanswered_widget(self.user, self.homework)
        self.assertIsNone(widget)

    def test_get_widget_progress(self):
        """Test get all widgets with answered status."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5
        )

        progress = HomeworkService.get_widget_progress(self.user, self.homework)
        self.assertEqual(progress.homework_id, self.homework.id)
        self.assertEqual(len(progress.widgets), 2)
        self.assertFalse(progress.all_pre_answered)
        self.assertFalse(progress.all_post_answered)

    def test_get_widget_progress_all_answered(self):
        """Test get widget progress when all are answered."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5, post_value=8
        )
        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget2, pre_value=7, post_value=9
        )

        progress = HomeworkService.get_widget_progress(self.user, self.homework)
        self.assertTrue(progress.all_pre_answered)
        self.assertTrue(progress.all_post_answered)

    def test_save_widget_response_pre(self):
        """Test saving pre widget response."""
        from homeworks.services import HomeworkService

        result = HomeworkService.save_widget_response(
            self.user, self.widget1.id, "pre", 7
        )
        self.assertTrue(result)

        response = self.WidgetResponse.objects.get(
            user=self.user, widget=self.widget1
        )
        self.assertEqual(response.pre_value, 7)
        self.assertIsNotNone(response.pre_submitted_at)

    def test_save_widget_response_post(self):
        """Test saving post widget response."""
        from homeworks.services import HomeworkService

        self.WidgetResponse.objects.create(
            user=self.user, widget=self.widget1, pre_value=5
        )

        result = HomeworkService.save_widget_response(
            self.user, self.widget1.id, "post", 9
        )
        self.assertTrue(result)

        response = self.WidgetResponse.objects.get(
            user=self.user, widget=self.widget1
        )
        self.assertEqual(response.post_value, 9)
        self.assertIsNotNone(response.post_submitted_at)


class HomeworkServiceUpdateWidgetsTest(TestCase):
    """Test cases for HomeworkService.update_homework with widget operations."""

    def setUp(self):
        from courses.models import Course

        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now(),
        )

    def test_update_homework_creates_widgets(self):
        """Test creating widgets when updating homework."""
        from homeworks.services import HomeworkService, HomeworkUpdateData

        update_data = HomeworkUpdateData(
            title="Updated Title",
            description="Updated Description",
            due_date=self.homework.due_date,
            sections_to_update=[],
            sections_to_create=[],
            sections_to_delete=[],
            widgets_to_create=[
                {"pre_prompt": "Pre prompt 1", "post_prompt": "Post prompt 1", "order": 1},
                {"pre_prompt": "Pre prompt 2", "post_prompt": "Post prompt 2", "order": 2},
            ],
        )

        result = HomeworkService.update_homework(self.homework.id, update_data)
        self.assertTrue(result.success)

        widgets = HomeworkProgressWidget.objects.filter(homework=self.homework)
        self.assertEqual(widgets.count(), 2)
        self.assertEqual(widgets[0].pre_prompt, "Pre prompt 1")
        self.assertEqual(widgets[1].pre_prompt, "Pre prompt 2")

    def test_update_homework_updates_widgets(self):
        """Test updating existing widgets."""
        from homeworks.services import HomeworkService, HomeworkUpdateData

        existing_widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Original Pre",
            post_prompt="Original Post",
            order=1,
        )

        update_data = HomeworkUpdateData(
            title="Updated Title",
            description="Updated Description",
            due_date=self.homework.due_date,
            sections_to_update=[],
            sections_to_create=[],
            sections_to_delete=[],
            widgets_to_update=[
                {
                    "id": existing_widget.id,
                    "pre_prompt": "Updated Pre",
                    "post_prompt": "Updated Post",
                    "order": 1,
                },
            ],
        )

        result = HomeworkService.update_homework(self.homework.id, update_data)
        self.assertTrue(result.success)

        existing_widget.refresh_from_db()
        self.assertEqual(existing_widget.pre_prompt, "Updated Pre")
        self.assertEqual(existing_widget.post_prompt, "Updated Post")

    def test_update_homework_deletes_widgets(self):
        """Test deleting widgets when updating homework."""
        from homeworks.services import HomeworkService, HomeworkUpdateData

        existing_widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="To be deleted",
            post_prompt="To be deleted",
            order=1,
        )
        widget_id = existing_widget.id

        update_data = HomeworkUpdateData(
            title="Updated Title",
            description="Updated Description",
            due_date=self.homework.due_date,
            sections_to_update=[],
            sections_to_create=[],
            sections_to_delete=[],
            widgets_to_delete=[widget_id],
        )

        result = HomeworkService.update_homework(self.homework.id, update_data)
        self.assertTrue(result.success)

        self.assertFalse(
            HomeworkProgressWidget.objects.filter(id=widget_id).exists()
        )