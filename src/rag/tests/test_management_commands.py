import hashlib
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Teacher, User
from courses.models import Course
from rag.models import CourseMaterial, CourseMaterialBlob, ProcessingStatus


class ProcessMaterialsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test", code="TST", description="Test", is_active=True
        )

    def _make_material(self, status=ProcessingStatus.PENDING) -> CourseMaterial:
        material = CourseMaterial.objects.create(
            course=self.course,
            title="Test PDF",
            original_filename="test.pdf",
            content_type="application/pdf",
            size=100,
            checksum=hashlib.sha256(b"data").hexdigest(),
            uploaded_by=self.teacher,
            processing_status=status,
        )
        CourseMaterialBlob.objects.create(material=material, data=b"data")
        return material

    def test_no_output_when_no_pending_materials(self):
        out = StringIO()
        call_command("process_materials", stdout=out)
        self.assertIn("No materials to process.", out.getvalue())

    def test_enqueues_pending_materials(self):
        self._make_material(status=ProcessingStatus.PENDING)
        self._make_material(status=ProcessingStatus.COMPLETED)

        out = StringIO()
        call_command("process_materials", stdout=out)
        self.assertIn("Enqueuing 1 material(s)", out.getvalue())
        self.assertIn("Done.", out.getvalue())

    def test_reindex_flag_enqueues_completed_materials(self):
        self._make_material(status=ProcessingStatus.COMPLETED)

        out = StringIO()
        call_command("process_materials", "--reindex", stdout=out)
        self.assertIn("Enqueuing 1 material(s)", out.getvalue())

    def test_material_id_flag_processes_single(self):
        mat = self._make_material(status=ProcessingStatus.COMPLETED)

        out = StringIO()
        call_command(
            "process_materials",
            f"--material-id={mat.id}",
            stdout=out,
        )
        self.assertIn(str(mat.id), out.getvalue())

    def test_material_id_unknown_shows_error(self):
        out = StringIO()
        call_command(
            "process_materials",
            "--material-id=00000000-0000-0000-0000-000000000000",
            stdout=out,
        )
        self.assertIn("not found", out.getvalue())
