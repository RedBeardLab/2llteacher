import hashlib

from django.test import TestCase

from accounts.models import Teacher, User
from courses.models import Course
from rag.models import CourseMaterial, CourseMaterialBlob, CourseMaterialChunk
from rag.services.chunker import PageText, Chunk
from rag.services.indexer import MaterialIndexer


class FakeExtractor:
    def __init__(self, pages=None):
        self.pages = pages or [PageText(page_number=1, text="Hello world.")]

    def __call__(self, pdf_data):
        return self.pages


class FakeChunker:
    def __init__(self, chunks=None):
        self.chunks = chunks or [
            Chunk(
                content="Hello world.",
                page_start=1,
                page_end=1,
                page_group_index=0,
                level="chunk",
            ),
            Chunk(
                content="Hello world.",
                page_start=1,
                page_end=1,
                page_group_index=None,
                level="page_group",
            ),
        ]

    def __call__(self, pages):
        return self.chunks


class FakeEmbedder:
    def __init__(self, dimension=1536):
        self.dimension = dimension

    def embed(self, texts):
        return [[0.001] * self.dimension for _ in texts]


class MaterialIndexerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test Course", code="TEST101", description="Test", is_active=True
        )
        self.material = CourseMaterial.objects.create(
            course=self.course,
            title="Test PDF",
            original_filename="test.pdf",
            content_type="application/pdf",
            size=100,
            checksum=hashlib.sha256(b"pdf-data").hexdigest(),
            uploaded_by=self.teacher,
        )
        CourseMaterialBlob.objects.create(material=self.material, data=b"pdf-data")

    def test_status_transitions_to_completed(self):
        extractor = FakeExtractor()
        chunker = FakeChunker()
        embedder = FakeEmbedder()
        indexer = MaterialIndexer(
            extractor=extractor, chunker=chunker, embedder=embedder
        )
        indexer.index(str(self.material.id))
        self.material.refresh_from_db()
        self.assertEqual(self.material.processing_status, "completed")
        self.assertEqual(self.material.pages, 1)

    def test_chunks_are_created(self):
        extractor = FakeExtractor()
        chunker = FakeChunker()
        embedder = FakeEmbedder()
        indexer = MaterialIndexer(
            extractor=extractor, chunker=chunker, embedder=embedder
        )
        indexer.index(str(self.material.id))
        chunks = CourseMaterialChunk.objects.filter(material=self.material)
        self.assertEqual(chunks.count(), 2)

    def test_chunks_have_embeddings(self):
        extractor = FakeExtractor()
        chunker = FakeChunker()
        embedder = FakeEmbedder()
        indexer = MaterialIndexer(
            extractor=extractor, chunker=chunker, embedder=embedder
        )
        indexer.index(str(self.material.id))
        for chunk in CourseMaterialChunk.objects.filter(material=self.material):
            self.assertIsNotNone(chunk.embedding)

    def test_status_transitions_to_failed_on_error(self):
        class FailingExtractor:
            def __call__(self, pdf_data):
                raise ValueError("Bad PDF")

        indexer = MaterialIndexer(
            extractor=FailingExtractor(), chunker=FakeChunker(), embedder=FakeEmbedder()
        )
        indexer.index(str(self.material.id))
        self.material.refresh_from_db()
        self.assertEqual(self.material.processing_status, "failed")
        self.assertIn("Bad PDF", self.material.error_message)

    def test_no_chunks_created_on_failure(self):
        class FailingExtractor:
            def __call__(self, pdf_data):
                raise RuntimeError("Corrupt file")

        indexer = MaterialIndexer(
            extractor=FailingExtractor(), chunker=FakeChunker(), embedder=FakeEmbedder()
        )
        indexer.index(str(self.material.id))
        self.assertEqual(
            CourseMaterialChunk.objects.filter(material=self.material).count(), 0
        )

    def test_existing_chunks_are_cleared_before_reindex(self):
        extractor = FakeExtractor()
        chunker = FakeChunker()
        embedder = FakeEmbedder()
        indexer = MaterialIndexer(
            extractor=extractor, chunker=chunker, embedder=embedder
        )
        indexer.index(str(self.material.id))
        self.assertEqual(
            CourseMaterialChunk.objects.filter(material=self.material).count(), 2
        )
        indexer.index(str(self.material.id))
        self.assertEqual(
            CourseMaterialChunk.objects.filter(material=self.material).count(), 2
        )

    def test_chunk_content_matches_what_chunker_produces(self):
        chunks = [
            Chunk(
                content="Custom chunk content.",
                page_start=2,
                page_end=3,
                page_group_index=0,
                level="chunk",
            ),
        ]
        extractor = FakeExtractor()
        chunker = FakeChunker(chunks=chunks)
        embedder = FakeEmbedder()
        indexer = MaterialIndexer(
            extractor=extractor, chunker=chunker, embedder=embedder
        )
        indexer.index(str(self.material.id))
        stored = CourseMaterialChunk.objects.filter(material=self.material).first()
        self.assertEqual(stored.content, "Custom chunk content.")
        self.assertEqual(stored.page_start, 2)
        self.assertEqual(stored.page_end, 3)
