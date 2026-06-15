import hashlib
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from accounts.models import Student, Teacher, TeacherAssistant
from courses.models import (
    Course,
    CourseEnrollment,
    CourseTeacher,
    CourseTeacherAssistant,
)
from rag.forms import (
    MAX_PDF_UPLOAD_SIZE,
    CourseMaterialUploadForm,
    title_from_filename,
)
from rag.models import CourseMaterial, CourseMaterialBlob

User = get_user_model()


def pdf_file(name: str = "lecture notes.pdf", data: bytes = b"%PDF-1.4\n"):
    return SimpleUploadedFile(name, data, content_type="application/pdf")


class CourseMaterialFormTests(TestCase):
    def test_valid_pdf_under_limit_is_accepted(self):
        form = CourseMaterialUploadForm(files=MultiValueDict({"pdf_files": [pdf_file()]}))

        self.assertTrue(form.is_valid(), form.errors)

    def test_non_pdf_is_rejected(self):
        upload = SimpleUploadedFile(
            "notes.txt", b"not a pdf", content_type="text/plain"
        )
        form = CourseMaterialUploadForm(files=MultiValueDict({"pdf_files": [upload]}))

        self.assertFalse(form.is_valid())
        self.assertIn("Only PDF files can be uploaded.", str(form.errors))

    def test_pdf_extension_with_wrong_content_type_is_rejected(self):
        upload = SimpleUploadedFile(
            "notes.pdf", b"%PDF-1.4\n", content_type="application/octet-stream"
        )
        form = CourseMaterialUploadForm(files=MultiValueDict({"pdf_files": [upload]}))

        self.assertFalse(form.is_valid())
        self.assertIn("Only PDF files can be uploaded.", str(form.errors))

    def test_oversized_pdf_is_rejected(self):
        upload = pdf_file(data=b"x" * (MAX_PDF_UPLOAD_SIZE + 1))
        form = CourseMaterialUploadForm(files=MultiValueDict({"pdf_files": [upload]}))

        self.assertFalse(form.is_valid())
        self.assertIn("PDF files must be 25 MB or smaller.", str(form.errors))

    def test_empty_pdf_is_rejected(self):
        form = CourseMaterialUploadForm(
            files=MultiValueDict({"pdf_files": [pdf_file(data=b"")]})
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Uploaded PDFs cannot be empty.", str(form.errors))

    def test_title_defaults_from_filename(self):
        self.assertEqual(title_from_filename("Week   01 notes.pdf"), "Week 01 notes")
        self.assertEqual(title_from_filename(".pdf"), ".pdf")
        self.assertEqual(title_from_filename(""), "Untitled PDF")


class CourseMaterialViewTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.other_teacher_user = User.objects.create_user(
            username="otherteacher",
            email="otherteacher@example.com",
            password="password123",
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.ta_user = User.objects.create_user(
            username="ta", email="ta@example.com", password="password123"
        )
        self.ta = TeacherAssistant.objects.create(user=self.ta_user)

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course",
            is_active=True,
        )
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )
        CourseTeacherAssistant.objects.create(
            course=self.course, teacher_assistant=self.ta
        )

    def create_material(
        self,
        title: str = "Lecture Notes",
        filename: str = "lecture.pdf",
        data: bytes = b"%PDF-1.4\nbody",
    ) -> CourseMaterial:
        material = CourseMaterial.objects.create(
            course=self.course,
            title=title,
            original_filename=filename,
            content_type="application/pdf",
            size=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            uploaded_by=self.teacher,
        )
        CourseMaterialBlob.objects.create(material=material, data=data)
        return material

    def test_material_model_strings_are_readable(self):
        material = self.create_material()

        self.assertEqual(str(material), "Lecture Notes (TEST101)")
        self.assertEqual(str(material.blob), f"Blob for {material.id}")

    def test_teacher_can_upload_multiple_pdfs(self):
        self.client.login(username="teacher", password="password123")
        response = self.client.post(
            reverse("courses:material-upload", kwargs={"course_id": self.course.id}),
            data={
                "pdf_files": [
                    pdf_file("Week 01.pdf", b"%PDF-1.4\none"),
                    pdf_file("Week 02.pdf", b"%PDF-1.4\ntwo"),
                ]
            },
        )

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        self.assertEqual(CourseMaterial.objects.filter(course=self.course).count(), 2)
        self.assertEqual(CourseMaterialBlob.objects.count(), 2)
        self.assertTrue(CourseMaterial.objects.filter(title="Week 01").exists())
        self.assertTrue(CourseMaterial.objects.filter(title="Week 02").exists())

    def test_invalid_upload_redirects_with_no_material_created(self):
        self.client.login(username="teacher", password="password123")
        response = self.client.post(
            reverse("courses:material-upload", kwargs={"course_id": self.course.id}),
            data={
                "pdf_files": [
                    SimpleUploadedFile(
                        "notes.txt", b"not a pdf", content_type="text/plain"
                    )
                ]
            },
        )

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        self.assertFalse(CourseMaterial.objects.exists())

    def test_upload_get_is_not_allowed(self):
        self.client.login(username="teacher", password="password123")
        response = self.client.get(
            reverse("courses:material-upload", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 405)

    def test_only_course_teacher_can_upload(self):
        self.client.login(username="otherteacher", password="password123")
        response = self.client.post(
            reverse("courses:material-upload", kwargs={"course_id": self.course.id}),
            data={"pdf_files": [pdf_file()]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_student_cannot_upload(self):
        self.client.login(username="student", password="password123")
        response = self.client.post(
            reverse("courses:material-upload", kwargs={"course_id": self.course.id}),
            data={"pdf_files": [pdf_file()]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseMaterial.objects.exists())

    def test_teacher_can_rename_material(self):
        material = self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.post(
            reverse(
                "courses:material-edit",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            ),
            data={"title": "Updated Title"},
        )

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        material.refresh_from_db()
        self.assertEqual(material.title, "Updated Title")

    def test_invalid_rename_redirects_without_changing_title(self):
        material = self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.post(
            reverse(
                "courses:material-edit",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            ),
            data={"title": ""},
        )

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        material.refresh_from_db()
        self.assertEqual(material.title, "Lecture Notes")

    def test_edit_get_is_not_allowed(self):
        material = self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.get(
            reverse(
                "courses:material-edit",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_non_teacher_cannot_rename_material(self):
        material = self.create_material()
        self.client.login(username="student", password="password123")

        response = self.client.post(
            reverse(
                "courses:material-edit",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            ),
            data={"title": "Updated Title"},
        )

        self.assertEqual(response.status_code, 403)
        material.refresh_from_db()
        self.assertEqual(material.title, "Lecture Notes")

    def test_teacher_can_hard_delete_material_and_blob(self):
        material = self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.post(
            reverse(
                "courses:material-delete",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            )
        )

        self.assertRedirects(
            response, reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        self.assertFalse(CourseMaterial.objects.filter(id=material.id).exists())
        self.assertFalse(CourseMaterialBlob.objects.filter(material=material).exists())

    def test_other_teacher_cannot_delete_material(self):
        material = self.create_material()
        self.client.login(username="otherteacher", password="password123")

        response = self.client.post(
            reverse(
                "courses:material-delete",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CourseMaterial.objects.filter(id=material.id).exists())
        self.assertTrue(CourseMaterialBlob.objects.filter(material=material).exists())

    def test_delete_get_is_not_allowed(self):
        material = self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.get(
            reverse(
                "courses:material-delete",
                kwargs={"course_id": self.course.id, "material_id": material.id},
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_pdf_url_serves_public_inline_pdf(self):
        data = b"%PDF-1.4\nbody"
        material = self.create_material(filename="lecture.pdf", data=data)
        self.client.logout()

        response = self.client.get(
            reverse(
                "materials:pdf",
                kwargs={"material_id": material.id, "checksum": material.checksum},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response["ETag"], f'"{material.checksum}"')
        self.assertEqual(
            response["Cache-Control"], "public, max-age=31536000, immutable"
        )
        self.assertEqual(response.content, data)

    def test_pdf_url_returns_304_for_matching_etag(self):
        material = self.create_material()

        response = self.client.get(
            reverse(
                "materials:pdf",
                kwargs={"material_id": material.id, "checksum": material.checksum},
            ),
            headers={"If-None-Match": f'"{material.checksum}"'},
        )

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response["ETag"], f'"{material.checksum}"')
        self.assertEqual(
            response["Cache-Control"], "public, max-age=31536000, immutable"
        )

    def test_pdf_url_returns_404_for_wrong_checksum(self):
        material = self.create_material()

        response = self.client.get(
            reverse(
                "materials:pdf",
                kwargs={"material_id": material.id, "checksum": "0" * 64},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_pdf_url_returns_404_for_missing_material(self):
        response = self.client.get(
            reverse(
                "materials:pdf",
                kwargs={"material_id": uuid.uuid4(), "checksum": "0" * 64},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_teacher_sees_material_management_controls(self):
        self.create_material()
        self.client.login(username="teacher", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Course Materials")
        self.assertContains(response, "Upload PDFs")
        self.assertContains(response, "Save")
        self.assertContains(response, "Delete")

    def test_student_sees_material_list_but_not_management_controls(self):
        self.create_material()
        self.client.login(username="student", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lecture Notes")
        self.assertNotContains(response, "Upload PDFs")
        self.assertNotContains(response, "Save")
        self.assertNotContains(response, "Delete")

    def test_ta_sees_material_list_but_not_management_controls(self):
        self.create_material()
        self.client.login(username="ta", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lecture Notes")
        self.assertNotContains(response, "Upload PDFs")
        self.assertNotContains(response, "Save")
        self.assertNotContains(response, "Delete")
