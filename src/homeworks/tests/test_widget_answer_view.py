"""
Tests for the WidgetAnswerView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from homeworks.models import Homework, HomeworkProgressWidget, Section
from conversations.models import (
    HomeworkProgressWidgetResponse,
    Conversation,
    Submission,
)
from accounts.models import User, Teacher, Student
from courses.models import Course, CourseEnrollment, CourseTeacher


class WidgetAnswerViewTestCase(TestCase):
    """Test cases for the WidgetAnswerView."""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.widget = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="How much do you know about this topic? (Pre)",
            post_prompt="How much do you now know about this topic? (Post)",
            order=1,
        )

        self.url = reverse(
            "homeworks:widget_answer", kwargs={"homework_id": self.homework.id}
        )

    def test_student_get_shows_pre_widget(self):
        """Test that student sees pre-assessment widget when not yet answered."""
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pre-Assessment")
        self.assertContains(response, "How much do you know about this topic? (Pre)")
        self.assertContains(response, "0")
        self.assertContains(response, "10")

    def test_student_get_shows_post_widget_after_pre_answered(self):
        """Test that student sees post-assessment after pre is answered."""
        HomeworkProgressWidgetResponse.objects.create(
            user=self.student_user,
            widget=self.widget,
            pre_value=5,
        )
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Post-Assessment")
        self.assertContains(
            response, "How much do you now know about this topic? (Post)"
        )
        self.assertContains(response, "0")
        self.assertContains(response, "10")

    def test_post_invalid_value_rejected(self):
        """Test that invalid values are rejected."""
        self.client.login(username="student", password="password")
        response = self.client.post(
            self.url,
            {
                "widget_id": str(self.widget.id),
                "value_type": "pre",
                "value": "11",
            },
        )
        self.assertEqual(response.status_code, 302)
        messages = (
            list(response.context["messages"])
            if hasattr(response, "context") and response.context
            else []
        )
        # Value should not be saved since 11 is out of range
        response_obj = HomeworkProgressWidgetResponse.objects.filter(
            user=self.student_user, widget=self.widget
        ).first()
        self.assertIsNone(response_obj)

    def test_not_enrolled_student_forbidden(self):
        """Test that students not enrolled in course cannot access."""
        new_user = User.objects.create_user(
            username="other", email="other@example.com", password="password"
        )
        other_student = Student.objects.create(user=new_user)

        self.client.login(username="other", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_homework_not_found(self):
        """Test that non-existent homework redirects to list."""
        self.client.login(username="student", password="password")
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        url = reverse("homeworks:widget_answer", kwargs={"homework_id": fake_uuid})
        response = self.client.get(url)
        # View redirects to list when homework not found
        self.assertEqual(response.status_code, 302)

    def test_after_pre_answered_redirects_to_homework_not_post(self):
        """After answering all pre, student should go to homework, not post."""
        # Create an interactive section so there's homework to do
        Section.objects.create(
            homework=self.homework,
            title="Interactive Section",
            order=1,
            section_type="conversation",
        )
        HomeworkProgressWidgetResponse.objects.create(
            user=self.student_user,
            widget=self.widget,
            pre_value=5,
        )
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse("homeworks:detail", kwargs={"homework_id": self.homework.id}),
        )

    def test_after_sections_completed_shows_post(self):
        """After completing all sections and all pre, student should see post."""
        section = Section.objects.create(
            homework=self.homework,
            title="Interactive Section",
            order=1,
            section_type="conversation",
        )
        HomeworkProgressWidgetResponse.objects.create(
            user=self.student_user,
            widget=self.widget,
            pre_value=5,
        )
        # Simulate completed homework: create conversation and submission
        conversation = Conversation.objects.create(
            user=self.student_user,
            section=section,
        )
        Submission.objects.create(
            conversation=conversation,
        )
        self.client.login(username="student", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Post-Assessment")
        self.assertContains(
            response, "How much do you now know about this topic? (Post)"
        )


class WidgetAnswerViewMultipleWidgetsTestCase(TestCase):
    """Test WidgetAnswerView with multiple widgets."""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.widget1 = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt 1",
            post_prompt="Post prompt 1",
            order=1,
        )
        self.widget2 = HomeworkProgressWidget.objects.create(
            homework=self.homework,
            pre_prompt="Pre prompt 2",
            post_prompt="Post prompt 2",
            order=2,
        )

        self.url = reverse(
            "homeworks:widget_answer", kwargs={"homework_id": self.homework.id}
        )

    def test_student_must_answer_all_pre_widgets(self):
        """Test that student must answer all pre widgets before sections."""
        self.client.login(username="student", password="password")

        # Only answer first widget
        HomeworkProgressWidgetResponse.objects.create(
            user=self.student_user,
            widget=self.widget1,
            pre_value=5,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Should still show widget2's pre_prompt, not redirect to sections
        self.assertContains(response, "Pre prompt 2")

    def test_post_updates_correct_widget(self):
        """Test that posting updates the correct widget."""
        self.client.login(username="student", password="password")

        # Answer first widget pre via ORM (to set it up)
        HomeworkProgressWidgetResponse.objects.create(
            user=self.student_user,
            widget=self.widget1,
            pre_value=5,
        )

        # Answer second widget pre via POST
        self.client.post(
            self.url,
            {
                "widget_id": str(self.widget2.id),
                "value_type": "pre",
                "value": "7",
            },
        )

        # Verify both responses exist with correct values
        response1 = HomeworkProgressWidgetResponse.objects.get(
            user=self.student_user, widget=self.widget1
        )
        # Widget2 response should have been created by POST
        response2 = HomeworkProgressWidgetResponse.objects.get(
            user=self.student_user, widget=self.widget2
        )

        self.assertEqual(response1.pre_value, 5)  # Unchanged
        self.assertEqual(response2.pre_value, 7)  # Created via POST
