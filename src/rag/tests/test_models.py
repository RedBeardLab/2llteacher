import hashlib

from django.db import IntegrityError
from django.test import TestCase

from courses.models import Course
from accounts.models import Teacher, User
from rag.models import (
    CourseMaterial,
    CourseMaterialBlob,
    CourseMaterialChunk,
    ProcessingStatus,
)


class CourseMaterialModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test Course", code="TEST101", description="Test", is_active=True
        )

    def create_material(self, **kwargs) -> CourseMaterial:
        fields = dict(
            course=self.course,
            title="Lecture Notes",
            original_filename="lecture.pdf",
            content_type="application/pdf",
            size=100,
            checksum=hashlib.sha256(b"pdf-data").hexdigest(),
            uploaded_by=self.teacher,
        )
        fields.update(kwargs)
        return CourseMaterial.objects.create(**fields)

    def test_default_processing_status_is_pending(self):
        material = self.create_material()
        self.assertEqual(material.processing_status, ProcessingStatus.PENDING)

    def test_error_message_defaults_to_empty(self):
        material = self.create_material()
        self.assertEqual(material.error_message, "")

    def test_pages_defaults_to_none(self):
        material = self.create_material()
        self.assertIsNone(material.pages)

    def test_str_representation(self):
        material = self.create_material()
        self.assertEqual(str(material), "Lecture Notes (TEST101)")

    def test_processing_status_can_be_set_to_failed(self):
        material = self.create_material()
        material.processing_status = ProcessingStatus.FAILED
        material.error_message = "Something went wrong"
        material.save()
        material.refresh_from_db()
        self.assertEqual(material.processing_status, ProcessingStatus.FAILED)
        self.assertEqual(material.error_message, "Something went wrong")

    def test_pages_is_updated_after_indexing(self):
        material = self.create_material()
        material.pages = 10
        material.save()
        material.refresh_from_db()
        self.assertEqual(material.pages, 10)

    def test_cascade_delete_blob(self):
        material = self.create_material()
        CourseMaterialBlob.objects.create(material=material, data=b"pdf-data")
        material.delete()
        self.assertEqual(CourseMaterialBlob.objects.count(), 0)

    def test_cascade_delete_chunks(self):
        material = self.create_material()
        Chunk = CourseMaterialChunk
        Chunk.objects.create(
            material=material,
            level=Chunk.Level.CHUNK,
            chunk_index=0,
            content="test",
            page_start=1,
            page_end=1,
        )
        material.delete()
        self.assertEqual(Chunk.objects.count(), 0)


class CourseMaterialChunkModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="teacher", password="password123")
        teacher = Teacher.objects.create(user=user)
        course = Course.objects.create(
            name="Test Course", code="TEST101", description="Test", is_active=True
        )
        self.material = CourseMaterial.objects.create(
            course=course,
            title="Lecture Notes",
            original_filename="lecture.pdf",
            content_type="application/pdf",
            size=100,
            checksum=hashlib.sha256(b"pdf-data").hexdigest(),
            uploaded_by=teacher,
        )
        CourseMaterialBlob.objects.create(material=self.material, data=b"pdf-data")

    def create_chunk(
        self, level="chunk", chunk_index=0, page_group_index=None
    ) -> CourseMaterialChunk:
        return CourseMaterialChunk.objects.create(
            material=self.material,
            level=level,
            chunk_index=chunk_index,
            content="Some extracted text content for the chunk.",
            page_start=1,
            page_end=1,
            page_group_index=page_group_index,
        )

    def test_chunk_str_representation(self):
        chunk = self.create_chunk()
        self.assertIn("chunk #0", str(chunk))
        self.assertIn(str(self.material.id), str(chunk))

    def test_unique_together_material_level_index(self):
        self.create_chunk(level="chunk", chunk_index=0)
        with self.assertRaises(IntegrityError):
            self.create_chunk(level="chunk", chunk_index=0)

    def test_same_index_different_level_is_allowed(self):
        self.create_chunk(level="chunk", chunk_index=0)
        self.create_chunk(level="page_group", chunk_index=0)

    def test_chunk_level_choices(self):
        chunk = self.create_chunk(level="chunk")
        self.assertEqual(chunk.level, "chunk")
        pg = self.create_chunk(level="page_group", chunk_index=1)
        self.assertEqual(pg.level, "page_group")

    def test_chunk_page_group_index_is_nullable(self):
        chunk = self.create_chunk()
        self.assertIsNone(chunk.page_group_index)

    def test_chunk_page_group_index_is_set(self):
        chunk = self.create_chunk(chunk_index=2, page_group_index=1)
        self.assertEqual(chunk.page_group_index, 1)

    def test_chunk_embedding_is_nullable(self):
        chunk = self.create_chunk()
        self.assertIsNone(chunk.embedding)

    def test_chunk_token_count_is_nullable(self):
        chunk = self.create_chunk()
        self.assertIsNone(chunk.token_count)

    def test_chunk_cascade_deletes_with_material(self):
        self.create_chunk()
        self.material.delete()
        self.assertEqual(CourseMaterialChunk.objects.count(), 0)

    def test_chunk_page_start_and_end(self):
        chunk = CourseMaterialChunk.objects.create(
            material=self.material,
            level="chunk",
            chunk_index=0,
            content="text",
            page_start=3,
            page_end=5,
        )
        self.assertEqual(chunk.page_start, 3)
        self.assertEqual(chunk.page_end, 5)
