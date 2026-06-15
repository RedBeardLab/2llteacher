import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User, Teacher, Student
from courses.models import Course, CourseTeacher, CourseEnrollment
from chat.models import Chat


class ChatDetailViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher1", password="pass123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(name="Test Course", code="TC101")
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        self.client.login(username="teacher1", password="pass123")

    def test_get_chat_page_returns_200(self):
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Course")
        self.assertContains(response, "Course Chat")

    def test_get_chat_creates_chat_when_none_exist(self):
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        self.client.get(url)
        self.assertTrue(
            Chat.objects.filter(
                user=self.user, course=self.course, is_deleted=False
            ).exists()
        )

    def test_get_chat_shows_messages(self):
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        response = self.client.get(url)
        self.assertContains(response, "AI Tutor")
        self.assertContains(response, "streamUrl")

    def test_get_chat_detail_shows_specific_chat(self):
        chat = Chat.objects.create(
            user=self.user, course=self.course, title="Test Chat"
        )
        url = reverse(
            "chat:course_chat_detail",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Chat")

    def test_unauthorized_access(self):
        User.objects.create_user(username="other", password="pass123")
        self.client.login(username="other", password="pass123")
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_student_access(self):
        student_user = User.objects.create_user(username="student1", password="pass123")
        student = Student.objects.create(user=student_user)
        CourseEnrollment.objects.create(
            course=self.course, student=student, is_active=True
        )
        self.client.login(username="student1", password="pass123")
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_sidebar_shows_all_chats(self):
        chat1 = Chat.objects.create(
            user=self.user, course=self.course, title="First Chat"
        )
        Chat.objects.create(user=self.user, course=self.course, title="Second Chat")
        url = reverse(
            "chat:course_chat_detail",
            kwargs={"course_id": self.course.id, "chat_id": chat1.id},
        )
        response = self.client.get(url)
        self.assertContains(response, "First Chat")
        self.assertContains(response, "Second Chat")

    def test_inactive_chat_not_shown_in_sidebar(self):
        Chat.objects.create(user=self.user, course=self.course, title="Active")
        Chat.objects.create(
            user=self.user, course=self.course, title="Deleted", is_deleted=True
        )
        url = reverse("chat:course_chat", kwargs={"course_id": self.course.id})
        response = self.client.get(url)
        self.assertContains(response, "Active")
        self.assertNotContains(response, "Deleted")


class ChatCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher1", password="pass123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(name="Test Course", code="TC101")
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        self.client.login(username="teacher1", password="pass123")

    def test_create_new_chat_redirects(self):
        url = reverse("chat:chat_create", kwargs={"course_id": self.course.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_create_new_chat_creates_chat(self):
        url = reverse("chat:chat_create", kwargs={"course_id": self.course.id})
        self.client.post(url)
        self.assertEqual(
            Chat.objects.filter(user=self.user, course=self.course).count(), 1
        )

    def test_create_new_chat_always_creates_fresh(self):
        url = reverse("chat:chat_create", kwargs={"course_id": self.course.id})
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(
            Chat.objects.filter(user=self.user, course=self.course).count(), 2
        )

    def test_create_new_chat_unauthorized(self):
        User.objects.create_user(username="other", password="pass123")
        self.client.login(username="other", password="pass123")
        url = reverse("chat:chat_create", kwargs={"course_id": self.course.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class ChatStreamViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher1", password="pass123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(name="Test Course", code="TC101")
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        self.client.login(username="teacher1", password="pass123")

    def _create_chat(self):
        return Chat.objects.create(user=self.user, course=self.course)

    def test_stream_returns_sse(self):
        chat = self._create_chat()
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data=json.dumps({"content": "Hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")

    def test_stream_empty_content_returns_400(self):
        chat = self._create_chat()
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data=json.dumps({"content": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_stream_missing_content_returns_400(self):
        chat = self._create_chat()
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_stream_invalid_json_returns_400(self):
        chat = self._create_chat()
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_stream_get_not_allowed(self):
        chat = self._create_chat()
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_stream_unauthorized(self):
        chat = self._create_chat()
        User.objects.create_user(username="other", password="pass123")
        self.client.login(username="other", password="pass123")
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data=json.dumps({"content": "Hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_stream_wrong_user_returns_404(self):
        other_user = User.objects.create_user(username="other2", password="pass123")
        chat = Chat.objects.create(user=other_user, course=self.course)
        url = reverse(
            "chat:stream",
            kwargs={"course_id": self.course.id, "chat_id": chat.id},
        )
        response = self.client.post(
            url,
            data=json.dumps({"content": "Hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
