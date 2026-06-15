from unittest.mock import Mock, patch

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, Teacher
from canvas.services.canvas_sync import CanvasSyncService
from canvas.views import CanvasMaterialSyncView
from courses.models import Course, CourseTeacher


class CanvasMaterialSyncViewTests(TestCase):
    """Tests for CanvasMaterialSyncView."""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username="t@uw.edu",
            email="t@uw.edu",
            password="pass",
        )
        self.teacher_profile = Teacher.objects.create(user=self.teacher)

        self.course = Course.objects.create(
            name="CS 101",
            code="CS101",
            description="Intro",
            canvas_course_id="42",
        )
        CourseTeacher.objects.create(course=self.course, teacher=self.teacher_profile)

        self.url = reverse(
            "canvas:material-sync", kwargs={"course_id": str(self.course.id)}
        )

        self.mock_service = Mock(spec=CanvasSyncService)
        self.patcher = patch.object(
            CanvasMaterialSyncView,
            "sync_service_factory",
            return_value=self.mock_service,
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _login(self):
        self.client.force_login(self.teacher)

    def test_requires_login(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

    def test_requires_teacher(self):
        student = User.objects.create_user(
            username="s@uw.edu", email="s@uw.edu", password="pass"
        )
        self.client.force_login(student)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_no_canvas_course_id(self):
        self._login()
        course = Course.objects.create(name="No Canvas", code="NONE", description="")
        url = reverse("canvas:material-sync", kwargs={"course_id": str(course.id)})

        response = self.client.post(url)

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": str(course.id)})
        )

    def test_no_files_selected(self):
        self._login()

        response = self.client.post(self.url, {})

        self.assertRedirects(
            response,
            reverse("courses:detail", kwargs={"course_id": str(self.course.id)}),
        )

    def test_happy_path(self):
        self._login()
        self.mock_service.sync_course_pdfs.return_value = {
            "synced": 2,
            "skipped": 0,
        }

        response = self.client.post(self.url, {"canvas_file_ids": ["1", "2"]})

        self.assertRedirects(
            response,
            reverse(
                "courses:detail",
                kwargs={"course_id": str(self.course.id)},
            ),
        )
        self.mock_service.sync_course_pdfs.assert_called_once()
        self.mock_service.sync_course_pdfs.assert_called_with(
            self.teacher, self.course, ["1", "2"]
        )

    def test_message_on_success(self):
        self._login()
        self.mock_service.sync_course_pdfs.return_value = {
            "synced": 2,
            "skipped": 0,
        }

        response = self.client.post(
            self.url, {"canvas_file_ids": ["1", "2"]}, follow=True
        )

        self.assertContains(response, "Imported 2 file(s)")
