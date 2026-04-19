"""
Tests for SectionAnswerSubmitView.

Students can submit answers to non-interactive sections.
Multiple submissions are allowed (each creates a new SectionAnswer row).
"""

from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Student, Teacher, User
from conversations.models import SectionAnswer
from courses.models import Course
from homeworks.models import Homework, Section


class SectionAnswerSubmitViewTests(TestCase):
    """Tests for POST /conversations/section/<id>/answer/"""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="pass"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.other_student_user = User.objects.create_user(
            username="other_student", email="other@example.com", password="pass"
        )
        self.other_student = Student.objects.create(user=self.other_student_user)

        self.course = Course.objects.create(
            name="Test Course", code="TC101", description=""
        )
        self.course.students.add(self.student)

        self.homework = Homework.objects.create(
            title="HW1",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What is 2+2?",
            order=1,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

        self.conv_section = Section.objects.create(
            homework=self.homework,
            title="Chat",
            content="Discuss.",
            order=2,
            section_type=Section.SECTION_TYPE_CONVERSATION,
        )

        self.url = lambda s: reverse(
            "conversations:answer_section", kwargs={"section_id": s.id}
        )

    # --- Auth ---

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # --- Happy path ---

    def test_enrolled_student_can_submit_answer(self):
        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SectionAnswer.objects.count(), 1)
        answer = SectionAnswer.objects.first()
        self.assertEqual(answer.answer, "Four")
        self.assertEqual(answer.user, self.student_user)
        self.assertEqual(answer.section, self.ni_section)

    def test_student_can_submit_multiple_answers(self):
        """Each submission creates a new row — re-submission is allowed."""
        self.client.login(username="student", password="pass")
        self.client.post(self.url(self.ni_section), {"answer": "First answer"})
        self.client.post(self.url(self.ni_section), {"answer": "Second answer"})

        self.assertEqual(SectionAnswer.objects.count(), 2)

    def test_redirects_to_next_interactive_section_after_submit(self):
        # setUp: ni_section order=1, conv_section order=2 → advance to conv_section
        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})

        expected = reverse(
            "homeworks:section_detail",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": self.conv_section.id,
            },
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_redirects_to_next_ni_section_after_submit(self):
        # Two NI sections: submitting first auto-advances to second
        ni2 = Section.objects.create(
            homework=self.homework,
            title="Q2",
            content="What is 3+3?",
            order=3,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )
        # Remove conv_section (order=2) so next after ni_section (order=1) is ni2 (order=3)
        self.conv_section.delete()

        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})

        expected = reverse(
            "homeworks:section_answer",
            kwargs={
                "homework_id": self.homework.id,
                "section_id": ni2.id,
            },
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_redirects_to_homework_detail_when_last_section(self):
        # Only the NI section exists (remove the conv_section)
        self.conv_section.delete()

        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})

        expected = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    # --- Empty answer ---

    def test_empty_answer_does_not_create_record(self):
        self.client.login(username="student", password="pass")
        self.client.post(self.url(self.ni_section), {"answer": "   "})
        self.assertEqual(SectionAnswer.objects.count(), 0)

    def test_empty_answer_redirects_back(self):
        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": ""})
        self.assertEqual(response.status_code, 302)

    # --- Authorization ---

    def test_teacher_cannot_submit_answer(self):
        self.client.login(username="teacher", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SectionAnswer.objects.count(), 0)

    def test_unenrolled_student_cannot_submit(self):
        self.client.login(username="other_student", password="pass")
        response = self.client.post(self.url(self.ni_section), {"answer": "Four"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SectionAnswer.objects.count(), 0)

    def test_conversation_section_returns_403(self):
        self.client.login(username="student", password="pass")
        response = self.client.post(self.url(self.conv_section), {"answer": "Four"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SectionAnswer.objects.count(), 0)


class SectionAnswerDetailViewTests(TestCase):
    """Tests for GET /conversations/section/<id>/answers/<student_id>/"""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.other_teacher_user = User.objects.create_user(
            username="other_teacher", email="other_teacher@example.com", password="pass"
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="pass"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course", code="TC101", description=""
        )
        self.course.students.add(self.student)

        from courses.models import CourseTeacher

        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )

        self.other_course = Course.objects.create(
            name="Other Course", code="OC101", description=""
        )
        CourseTeacher.objects.create(
            course=self.other_course, teacher=self.other_teacher, role="owner"
        )

        self.homework = Homework.objects.create(
            title="HW1",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What is 2+2?",
            order=1,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

        self.url = reverse(
            "conversations:section_answers",
            kwargs={"section_id": self.ni_section.id, "student_id": self.student.id},
        )

    def test_teacher_of_course_can_view(self):
        self.client.login(username="teacher", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "conversations/section_answers.html")

    def test_teacher_from_other_course_forbidden(self):
        self.client.login(username="other_teacher", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_student_forbidden(self):
        self.client.login(username="student", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_shows_all_answers_newest_first(self):
        SectionAnswer.objects.create(
            user=self.student_user, section=self.ni_section, answer="First answer"
        )
        SectionAnswer.objects.create(
            user=self.student_user, section=self.ni_section, answer="Second answer"
        )

        self.client.login(username="teacher", password="pass")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First answer")
        self.assertContains(response, "Second answer")
        # Newest first: "Second answer" should appear before "First answer" in content
        content = response.content.decode()
        self.assertLess(content.index("Second answer"), content.index("First answer"))

    def test_empty_page_when_no_answers(self):
        self.client.login(username="teacher", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not submitted any answers")
