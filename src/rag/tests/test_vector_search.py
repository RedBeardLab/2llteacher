import struct

from django.test import TestCase

from accounts.models import Teacher, User
from courses.models import Course
from rag.models import CourseMaterial, CourseMaterialBlob, CourseMaterialChunk
from rag.services.vector_search import search_similar


class SearchSimilarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test Course", code="TEST101", description="Test", is_active=True
        )
        self.other_course = Course.objects.create(
            name="Other", code="OTHER", description="Other", is_active=True
        )

    def _make_material(self, course=None) -> CourseMaterial:
        course = course or self.course
        material = CourseMaterial.objects.create(
            course=course,
            title="Test PDF",
            original_filename="test.pdf",
            content_type="application/pdf",
            size=100,
            checksum="abc",
            uploaded_by=self.teacher,
        )
        CourseMaterialBlob.objects.create(material=material, data=b"pdf")
        return material

    def _make_chunk(
        self, material, content: str, vec: list[float], level="chunk", chunk_index=0
    ):
        blob = struct.pack(f"{len(vec)}f", *vec)
        return CourseMaterialChunk.objects.create(
            material=material,
            level=level,
            chunk_index=chunk_index,
            content=content,
            page_start=1,
            page_end=1,
            embedding=blob,
        )

    def test_search_returns_scored_results(self):
        material = self._make_material()
        self._make_chunk(
            material, "The cat sat on the mat.", [0.1, 0.2, 0.3], chunk_index=0
        )
        self._make_chunk(
            material, "Dogs play in the park.", [0.9, 0.8, 0.7], chunk_index=1
        )

        results = search_similar([0.1, 0.2, 0.2], self.course.id, top_k=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].content, "The cat sat on the mat.")

    def test_search_returns_empty_for_no_chunks(self):
        results = search_similar([0.1, 0.2, 0.3], self.course.id, top_k=5)
        self.assertEqual(results, [])

    def test_search_only_returns_chunks_for_given_course(self):
        material = self._make_material(course=self.other_course)
        self._make_chunk(
            material, "Other course content.", [0.1, 0.2, 0.3], chunk_index=0
        )

        results = search_similar([0.1, 0.2, 0.3], self.course.id, top_k=5)
        self.assertEqual(results, [])

    def test_search_filters_by_level(self):
        material = self._make_material()
        self._make_chunk(
            material, "A chunk.", [0.1, 0.2, 0.3], level="chunk", chunk_index=0
        )
        self._make_chunk(
            material, "A group.", [0.1, 0.2, 0.3], level="page_group", chunk_index=0
        )

        results = search_similar(
            [0.1, 0.2, 0.3], self.course.id, level="page_group", top_k=5
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].level, "page_group")

    def test_search_returns_top_k_results(self):
        material = self._make_material()
        for i in range(5):
            self._make_chunk(
                material, f"Content {i}.", [0.1, 0.2, float(i) / 10], chunk_index=i
            )

        results = search_similar([0.1, 0.2, 0.0], self.course.id, top_k=3)
        self.assertEqual(len(results), 3)

    def test_results_are_sorted_by_similarity(self):
        material = self._make_material()
        self._make_chunk(material, "Far away.", [0.9, 0.9, 0.9], chunk_index=0)
        self._make_chunk(material, "Close match.", [0.1, 0.2, 0.1], chunk_index=1)

        results = search_similar([0.1, 0.2, 0.1], self.course.id, top_k=5)
        self.assertEqual(results[0].content, "Close match.")
