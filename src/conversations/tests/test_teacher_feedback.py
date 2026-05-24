"""Tests for the TeacherFeedback model, form, view, and templates."""

from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Student, Teacher, User
from conversations.forms import TeacherFeedbackForm
from conversations.models import Conversation, TeacherFeedback
from courses.models import Course, CourseEnrollment, CourseTeacher
from homeworks.models import Homework, Section


class TeacherFeedbackBase(TestCase):
    """Shared fixtures."""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="t1",
            email="t1@example.com",
            password="password123",
            first_name="T",
            last_name="One",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.other_teacher_user = User.objects.create_user(
            username="t2",
            email="t2@example.com",
            password="password123",
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        self.student_user = User.objects.create_user(
            username="s1",
            email="s1@example.com",
            password="password123",
        )
        self.student = Student.objects.create(user=self.student_user)

        self.other_student_user = User.objects.create_user(
            username="s2",
            email="s2@example.com",
            password="password123",
        )
        self.other_student = Student.objects.create(user=self.other_student_user)

        self.course = Course.objects.create(name="C1", code="C1", description="")
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(course=self.course, student=self.student)
        CourseEnrollment.objects.create(course=self.course, student=self.other_student)

        self.homework = Homework.objects.create(
            title="H1",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )
        self.section = Section.objects.create(
            homework=self.homework, title="Sec 1", content="content", order=1
        )

        self.conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        self.detail_url = reverse(
            "conversations:detail",
            kwargs={"conversation_id": self.conversation.id},
        )
        self.submit_url = reverse(
            "conversations:submit_feedback",
            kwargs={"conversation_id": self.conversation.id},
        )


class TeacherFeedbackFormTests(TeacherFeedbackBase):
    def test_form_requires_feedback_text(self):
        form = TeacherFeedbackForm(data={"feedback_type": "general", "feedback": "   "})
        self.assertFalse(form.is_valid())
        self.assertIn("feedback", form.errors)

    def test_form_valid_with_text(self):
        form = TeacherFeedbackForm(
            data={"feedback_type": "good_work", "feedback": "Nice work."}
        )
        self.assertTrue(form.is_valid())


class TeacherFeedbackCreateTests(TeacherFeedbackBase):
    def test_teacher_can_create_feedback(self):
        self.client.login(username="t1", password="password123")
        resp = self.client.post(
            self.submit_url,
            data={"feedback_type": "needs_revision", "feedback": "Please clarify."},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TeacherFeedback.objects.count(), 1)
        fb = TeacherFeedback.objects.get()
        self.assertEqual(fb.teacher_id, self.teacher_user.id)
        self.assertEqual(fb.student_id, self.student_user.id)
        self.assertEqual(fb.section_id, self.section.id)
        self.assertEqual(fb.conversation_id, self.conversation.id)
        self.assertEqual(fb.feedback_type, "needs_revision")
        self.assertEqual(fb.feedback, "Please clarify.")

    def test_teacher_can_update_existing_feedback(self):
        self.client.login(username="t1", password="password123")
        self.client.post(
            self.submit_url,
            data={"feedback_type": "general", "feedback": "first"},
        )
        self.client.post(
            self.submit_url,
            data={"feedback_type": "good_work", "feedback": "second"},
        )
        self.assertEqual(TeacherFeedback.objects.count(), 1)
        fb = TeacherFeedback.objects.get()
        self.assertEqual(fb.feedback, "second")
        self.assertEqual(fb.feedback_type, "good_work")

    def test_empty_feedback_rejected(self):
        self.client.login(username="t1", password="password123")
        resp = self.client.post(
            self.submit_url,
            data={"feedback_type": "general", "feedback": "   "},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TeacherFeedback.objects.count(), 0)

    def test_student_cannot_submit_feedback(self):
        self.client.login(username="s1", password="password123")
        resp = self.client.post(
            self.submit_url,
            data={"feedback_type": "general", "feedback": "hi"},
        )
        # teacher_required redirects non-teachers
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(TeacherFeedback.objects.count(), 0)

    def test_unrelated_teacher_cannot_submit_feedback(self):
        self.client.login(username="t2", password="password123")
        resp = self.client.post(
            self.submit_url,
            data={"feedback_type": "general", "feedback": "x"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(TeacherFeedback.objects.count(), 0)

    def test_feedback_not_allowed_on_teacher_test_conversation(self):
        # A teacher's own conversation is a "teacher test"
        teacher_conv = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )
        self.client.login(username="t1", password="password123")
        url = reverse(
            "conversations:submit_feedback",
            kwargs={"conversation_id": teacher_conv.id},
        )
        resp = self.client.post(url, data={"feedback_type": "general", "feedback": "x"})
        self.assertEqual(resp.status_code, 403)


class TeacherFeedbackVisibilityTests(TeacherFeedbackBase):
    def _create_feedback(self):
        return TeacherFeedback.objects.create(
            teacher=self.teacher_user,
            student=self.student_user,
            section=self.section,
            conversation=self.conversation,
            feedback="Strong reasoning — well done.",
            feedback_type="good_work",
        )

    def test_owner_student_sees_their_feedback(self):
        self._create_feedback()
        self.client.login(username="s1", password="password123")
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Strong reasoning")
        self.assertContains(resp, "Teacher Feedback")

    def test_other_student_cannot_see_feedback(self):
        self._create_feedback()
        # Another enrolled student is not authorized to view this conversation
        # at all — ensure the conversation detail page denies them so they
        # never see the feedback.
        self.client.login(username="s2", password="password123")
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_sees_feedback(self):
        self._create_feedback()
        self.client.login(username="t1", password="password123")
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Strong reasoning")
        self.assertContains(resp, "Teacher Feedback")

    def test_teacher_form_shows_update_button_when_feedback_exists(self):
        self._create_feedback()
        self.client.login(username="t1", password="password123")
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Update Feedback")
