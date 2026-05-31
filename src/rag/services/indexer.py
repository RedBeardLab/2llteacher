import logging
import struct
from typing import Callable

from django.shortcuts import get_object_or_404

from rag.models import CourseMaterial, CourseMaterialChunk, ProcessingStatus
from rag.services.chunker import Chunk, PageText

logger = logging.getLogger(__name__)

PageExtractor = Callable[[bytes], list[PageText]]
Chunker = Callable[[list[PageText]], list[Chunk]]


class Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _embedding_to_blob(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


class MaterialIndexer:
    def __init__(
        self,
        *,
        extractor: PageExtractor,
        chunker: Chunker,
        embedder: Embedder,
    ) -> None:
        self._extract = extractor
        self._chunk = chunker
        self._embedder = embedder

    def index(self, material_id: str) -> None:
        material = get_object_or_404(CourseMaterial, id=material_id)

        material.processing_status = ProcessingStatus.PROCESSING
        material.error_message = ""
        material.save(update_fields=["processing_status", "error_message"])

        try:
            blob = material.blob
            pages = self._extract(blob.data)
            chunks = self._chunk(pages)

            chunk_texts = [c.content for c in chunks]
            embeddings = self._embedder.embed(chunk_texts)

            CourseMaterialChunk.objects.filter(material=material).delete()

            chunk_records = [
                CourseMaterialChunk(
                    material=material,
                    level=c.level,
                    chunk_index=ci,
                    page_group_index=c.page_group_index,
                    content=c.content,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    embedding=_embedding_to_blob(embeddings[ci]),
                    token_count=len(c.content.split()),
                )
                for ci, c in enumerate(chunks)
            ]
            CourseMaterialChunk.objects.bulk_create(chunk_records)

            material.processing_status = ProcessingStatus.COMPLETED
            material.pages = len(pages)
            material.save(update_fields=["processing_status", "pages"])

        except Exception:
            logger.exception("Failed to index material %s", material_id)
            material.processing_status = ProcessingStatus.FAILED
            import traceback

            material.error_message = traceback.format_exc()
            material.save(update_fields=["processing_status", "error_message"])
