from .pdf_extractor import PageText


class Chunk:
    def __init__(
        self,
        content: str,
        page_start: int,
        page_end: int,
        page_group_index: int | None,
        level: str,
        chunk_index: int = 0,
    ) -> None:
        self.content = content
        self.page_start = page_start
        self.page_end = page_end
        self.page_group_index = page_group_index
        self.level = level
        self.chunk_index = chunk_index


def _generate_page_groups(
    pages: list[PageText],
    *,
    page_group_size: int,
    page_group_stride: int,
) -> list[Chunk]:
    groups: list[Chunk] = []
    group_index = 0
    start = 0
    while start < len(pages):
        end = min(start + page_group_size, len(pages))
        group_pages = pages[start:end]
        combined = "\n\n".join(p.text for p in group_pages)
        groups.append(
            Chunk(
                content=combined,
                page_start=group_pages[0].page_number,
                page_end=group_pages[-1].page_number,
                page_group_index=None,
                level="page_group",
                chunk_index=len(groups),
            )
        )
        group_index += 1
        start += page_group_stride
    return groups


def _split_text(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    if not text:
        return []
    if len(text) <= chunk_size:
        return [(text, 0, len(text))]

    result: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        result.append((text[start:end], start, end))
        if end == len(text):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = start + chunk_size
        if next_start >= len(text):
            next_start = len(text) - chunk_size
            if next_start <= start:
                break
        start = next_start
    return result


def _generate_chunks(
    pages: list[PageText],
    *,
    chunk_size: int,
    overlap: int,
    page_groups: list[Chunk],
) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_index = 0
    for page in pages:
        segments = _split_text(page.text, chunk_size, overlap)
        for segment_text, _seg_start, _seg_end in segments:
            if not segment_text.strip():
                continue
            parent_group = None
            for gi, group in enumerate(page_groups):
                if group.page_start <= page.page_number <= group.page_end:
                    parent_group = gi
                    break
            chunks.append(
                Chunk(
                    content=segment_text.strip(),
                    page_start=page.page_number,
                    page_end=page.page_number,
                    page_group_index=parent_group,
                    level="chunk",
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1
    return chunks


def chunk_hierarchical(
    pages: list[PageText],
    *,
    chunk_size: int = 1000,
    overlap: int = 200,
    page_group_size: int = 3,
    page_group_stride: int = 2,
) -> list[Chunk]:
    if not pages:
        return []
    page_groups = _generate_page_groups(
        pages,
        page_group_size=page_group_size,
        page_group_stride=page_group_stride,
    )
    chunks = _generate_chunks(
        pages,
        chunk_size=chunk_size,
        overlap=overlap,
        page_groups=page_groups,
    )
    return page_groups + chunks
