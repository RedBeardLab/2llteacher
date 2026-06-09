import struct
from uuid import UUID

from rag.models import CourseMaterial, CourseMaterialChunk


class ScoredChunk:
    def __init__(
        self,
        chunk_id: str,
        material_id: str,
        material_title: str,
        content: str,
        page_start: int,
        page_end: int,
        level: str,
        score: float,
        material_checksum: str = "",
    ) -> None:
        self.chunk_id = chunk_id
        self.material_id = material_id
        self.material_title = material_title
        self.content = content
        self.page_start = page_start
        self.page_end = page_end
        self.level = level
        self.score = score
        self.material_checksum = material_checksum


def search_similar(
    query_embedding: list[float],
    course_id: UUID,
    *,
    level: str = "chunk",
    top_k: int = 5,
) -> list[ScoredChunk]:
    material_ids = list(
        CourseMaterial.objects.filter(course_id=course_id).values_list("id", flat=True)
    )
    if not material_ids:
        return []

    chunks = CourseMaterialChunk.objects.filter(
        material_id__in=material_ids,
        level=level,
    ).select_related("material").only(
        "id", "material_id", "content", "page_start", "page_end", "level", "embedding",
        "material__checksum",
    )

    material_cache: dict[str, tuple[str, str]] = {}
    for mid in material_ids:
        mid_str = str(mid)
        try:
            mat = CourseMaterial.objects.only("title", "checksum").get(id=mid)
            material_cache[mid_str] = (mat.title, mat.checksum)
        except CourseMaterial.DoesNotExist:
            material_cache[mid_str] = ("Unknown", "")

    scored: list[ScoredChunk] = []
    for chunk in chunks:
        if chunk.embedding is None:
            continue

        mid_str = str(chunk.material_id)

        try:
            stored_vec = list(
                struct.unpack(f"{len(query_embedding)}f", bytes(chunk.embedding))
            )
        except (struct.error, TypeError):
            continue

        distance = sum((a - b) ** 2 for a, b in zip(stored_vec, query_embedding))
        title, checksum = material_cache.get(mid_str, ("Unknown", ""))

        scored.append(
            ScoredChunk(
                chunk_id=str(chunk.id),
                material_id=mid_str,
                material_title=title,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                level=chunk.level,
                score=float(distance),
                material_checksum=checksum,
            )
        )

    scored.sort(key=lambda x: x.score)
    return scored[:top_k]
