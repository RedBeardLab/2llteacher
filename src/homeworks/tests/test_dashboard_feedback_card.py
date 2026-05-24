"""Tests for the student dashboard "Recent Teacher Feedback" card."""

from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Student, Teacher, User
from conversations.models import Conversation, TeacherFeedback
from courses.models import Course, CourseEnrollment, CourseTeacher
from homeworks.models import Homework, Section


class StudentDashboardFeedbackCardTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="t1", email="t1@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="s1", email="s1@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.other_student_user = User.objects.create_user(
            username="s2", email="s2@example.com", password="password123"
        )
        self.other_student = Student.objects.create(user=self.other_student_user)

        self.course = Course.objects.create(name="C1", code="C1", description="")
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(course=self.course, student=self.student)
        CourseEnrollment.objects.create(course=self.course, student=self.other_student)

        self.homework = Homework.objects.create(
            title="HW Title",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section = Section.objects.create(
            homework=self.homework,
            title="Section One",
            content="content",
            order=1,
        )
        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        self.list_url = reverse("homeworks:list")

    def test_no_feedback_shows_reasoning_reminder(self):
        self.client.login(username="s1", password="password123")
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Reasoning Reminder")
        self.assertNotContains(resp, "Recent Teacher Feedback")

    def test_feedback_shows_on_dashboard_for_owning_student(self):
        TeacherFeedback.objects.create(
            teacher=self.teacher_user,
            student=self.student_user,
            section=self.section,
            conversation=self.conversation,
            feedback="Clarify the regression assumptions.",
            feedback_type="needs_revision",
        )
        self.client.login(username="s1", password="password123")
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Recent Teacher Feedback")
        self.assertContains(resp, "Clarify the regression assumptions.")
        self.assertContains(resp, "Section One")
        self.assertContains(resp, "Needs revision")
        # Link to review feedback (the conversation) is present.
        self.assertContains(
            resp,
            reverse(
                "conversations:detail", kwargs={"conversation_id": self.conversation.id}
            ),
        )
        # Reasoning Reminder fallback should not appear.
        self.assertNotContains(resp, "Reasoning Reminder")

    def test_other_students_feedback_is_not_shown(self):
        # Create feedback addressed to the *other* student.
        other_conv = Conversation.objects.create(
            user=self.other_student_user, section=self.section
        )
        TeacherFeedback.objects.create(
            teacher=self.teacher_user,
            student=self.other_student_user,
            section=self.section,
            conversation=other_conv,
            feedback="Private note for s2 only.",
            feedback_type="general",
        )
        self.client.login(username="s1", password="password123")
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        # Other student's feedback must not leak.
        self.assertNotContains(resp, "Private note for s2 only.")
        # And without their own feedback, s1 sees the reminder.
        self.assertContains(resp, "Reasoning Reminder")

    def test_latest_feedback_is_shown_when_multiple_exist(self):
        # First (older) feedback.
        TeacherFeedback.objects.create(
            teacher=self.teacher_user,
            student=self.student_user,
            section=self.section,
            conversation=self.conversation,
            feedback="Older note.",
            feedback_type="general",
        )
        # Second conversation + newer feedback.
        newer_section = Section.objects.create(
            homework=self.homework, title="Section Two", content="x", order=2
        )
        newer_conv = Conversation.objects.create(
            user=self.student_user, section=newer_section
        )
        TeacherFeedback.objects.create(
            teacher=self.teacher_user,
            student=self.student_user,
            section=newer_section,
            conversation=newer_conv,
            feedback="Latest reasoning is great.",
            feedback_type="good_work",
        )
        self.client.login(username="s1", password="password123")
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Latest reasoning is great.")
        self.assertContains(resp, "Section Two")
        self.assertNotContains(resp, "Older note.")
