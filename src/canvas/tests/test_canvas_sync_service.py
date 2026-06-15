from unittest.mock import Mock, patch

from django.test import TestCase

import requests

from accounts.models import User
from canvas.canvas_service import CanvasOAuth2Service, CanvasFile
from canvas.services.canvas_sync import CanvasSyncService
from canvas.models import CanvasFileSync
from courses.models import Course
from rag.models import CourseMaterial


class CanvasSyncServiceTests(TestCase):
    """Tests for CanvasSyncService."""

    def setUp(self):
        self.canvas_mock = Mock(spec=CanvasOAuth2Service)
        self.download_mock = Mock(spec=lambda url: b"")
        self.service = CanvasSyncService(
            canvas_service=self.canvas_mock,
            download=self.download_mock,
        )
        self.user = User.objects.create_user(
            username="teacher@uw.edu",
            email="teacher@uw.edu",
            password="pass",
        )
        self.course = Course.objects.create(
            name="CS 101",
            code="CS101",
            description="Intro",
            canvas_course_id="42",
        )

    def _make_file(
        self,
        file_id: str,
        filename: str = "lecture1.pdf",
        display_name: str = "Lecture 1",
        url: str | None = "https://canvas.test/files/1",
        size: int = 1024,
    ) -> CanvasFile:
        return CanvasFile(
            file_id=file_id,
            filename=filename,
            display_name=display_name,
            url=url,
            size=size,
        )

    def test_token_unavailable_raises(self):
        self.canvas_mock.get_or_refresh_token.return_value = None

        with self.assertRaisesRegex(RuntimeError, "Canvas token unavailable"):
            self.service.sync_course_pdfs(self.user, self.course, ["1"])

    def test_no_canvas_course_id_asserts(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        course = Course.objects.create(name="No Canvas", code="NONE", description="")

        with self.assertRaises(AssertionError):
            self.service.sync_course_pdfs(self.user, course, ["1"])

    def test_skips_unselected_file(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]

        result = self.service.sync_course_pdfs(self.user, self.course, ["99"])

        self.assertEqual(result, {"synced": 0, "skipped": 0})

    def test_skips_missing_public_url(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]
        self.canvas_mock.get_file_public_url.return_value = None

        result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})

    def test_skips_non_pdf(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1", filename="notes.txt", url="https://example.com/txt"),
        ]

        result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})

    def test_skips_already_synced(self):
        CanvasFileSync.objects.create(
            course=self.course,
            canvas_file_id="1",
            display_name="Lecture 1",
            filename="lecture1.pdf",
            size=1024,
            checksum="abc",
        )
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]

        result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})

    def test_skips_download_failure(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]
        self.canvas_mock.get_file_public_url.return_value = "https://public.url/pdf"
        self.download_mock.side_effect = requests.RequestException("timeout")

        result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})

    def test_skips_duplicate_checksum(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]
        self.canvas_mock.get_file_public_url.return_value = "https://public.url/pdf"
        self.download_mock.return_value = b"pdf content"
        CourseMaterial.objects.create(
            course=self.course,
            title="Duplicate",
            original_filename="dup.pdf",
            content_type="application/pdf",
            checksum="9cca06ce6b093aacad4657a5198cfceb531e04c69d602b30d1d05749173eae5f",
            size=11,
        )

        result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})

    def test_happy_path(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
            self._make_file("2"),
        ]

        def _public_url(file_id: str, token: str) -> str:
            return f"https://public.url/{file_id}"

        self.canvas_mock.get_file_public_url.side_effect = _public_url

        def _download(url: str) -> bytes:
            return b"pdf content" if "/1" in url else b"other content"

        self.download_mock.side_effect = _download

        result = self.service.sync_course_pdfs(self.user, self.course, ["1", "2"])

        self.assertEqual(result, {"synced": 2, "skipped": 0})

        materials = CourseMaterial.objects.filter(course=self.course)
        self.assertEqual(materials.count(), 2)
        self.assertEqual(materials.first().original_filename, "lecture1.pdf")

        syncs = CanvasFileSync.objects.filter(course=self.course)
        self.assertEqual(syncs.count(), 2)

    def test_database_error_skips(self):
        self.canvas_mock.get_or_refresh_token.return_value = "tok"
        self.canvas_mock.get_course_files.return_value = [
            self._make_file("1"),
        ]
        self.canvas_mock.get_file_public_url.return_value = "https://public.url/pdf"
        self.download_mock.return_value = b"pdf content"

        with patch.object(
            CourseMaterial.objects, "create", side_effect=Exception("DB down")
        ):
            result = self.service.sync_course_pdfs(self.user, self.course, ["1"])

        self.assertEqual(result, {"synced": 0, "skipped": 1})
