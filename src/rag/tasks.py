import httpx
from openai import OpenAI

from django.conf import settings

from rag.huey import huey
from rag.services.embeddings import Embedder
from rag.services.indexer import MaterialIndexer
from rag.services.pdf_extractor import extract_pages
from rag.services.chunker import chunk_hierarchical
from rag.services.api_key import resolve_embedding_api_key


@huey.task(retries=3, retry_delay=60)
def index_course_material(material_id: str, course_id: str) -> None:
    api_key = resolve_embedding_api_key(course_id)
    if not api_key:
        from rag.models import CourseMaterial

        mat = CourseMaterial.objects.get(id=material_id)
        mat.processing_status = "failed"
        mat.error_message = (
            "No active LLM config with an API key found for this course."
        )
        mat.save(update_fields=["processing_status", "error_message"])
        return

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=httpx.Timeout(
            connect=settings.LLM_API_CONNECTION_TIMEOUT,
            read=settings.LLM_API_TIMEOUT,
            write=10.0,
            pool=5.0,
        ),
    )
    embedder = Embedder(
        client=client,
        model=settings.EMBEDDING_MODEL,
    )
    indexer = MaterialIndexer(
        extractor=extract_pages,
        chunker=chunk_hierarchical,
        embedder=embedder,
    )
    indexer.index(material_id)
