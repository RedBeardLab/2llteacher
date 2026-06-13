from django.test import SimpleTestCase

from rag.services.chunker import chunk_hierarchical, PageText


class ChunkHierarchicalTests(SimpleTestCase):
    def _chunks(self, chunks):
        return [c for c in chunks if c.level == "chunk"]

    def _page_groups(self, chunks):
        return [c for c in chunks if c.level == "page_group"]

    def test_single_page_short_text_returns_one_chunk(self):
        pages = [PageText(page_number=1, text="Short text.")]
        chunks = self._chunks(chunk_hierarchical(pages, chunk_size=1000, overlap=0))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].level, "chunk")
        self.assertEqual(chunks[0].page_start, 1)
        self.assertEqual(chunks[0].page_end, 1)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].content, "Short text.")

    def test_long_page_is_split_into_multiple_chunks(self):
        pages = [PageText(page_number=1, text="Hello. " * 200)]
        chunks = self._chunks(chunk_hierarchical(pages, chunk_size=500, overlap=0))
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertEqual(c.level, "chunk")
            self.assertLessEqual(len(c.content), 510)

    def test_chunks_have_overlap(self):
        words = [f"w{i}" for i in range(500)]
        text = " ".join(words)
        pages = [PageText(page_number=1, text=text)]
        chunks = self._chunks(chunk_hierarchical(pages, chunk_size=500, overlap=100))
        self.assertGreater(len(chunks), 1)

        first_words = set(chunks[0].content.split())
        second_words = set(chunks[1].content.split())
        overlap_count = len(first_words & second_words)
        self.assertGreater(overlap_count, 0)

    def test_page_group_level_is_created(self):
        pages = [
            PageText(page_number=1, text="Page one."),
            PageText(page_number=2, text="Page two."),
            PageText(page_number=3, text="Page three."),
        ]
        chunks = chunk_hierarchical(pages, page_group_size=3, page_group_stride=2)
        page_groups = self._page_groups(chunks)
        self.assertGreater(len(page_groups), 0)
        for pg in page_groups:
            self.assertEqual(pg.level, "page_group")
            self.assertIsNone(pg.page_group_index)

    def test_page_group_combines_text_from_multiple_pages(self):
        pages = [
            PageText(page_number=1, text="Page one."),
            PageText(page_number=2, text="Page two."),
            PageText(page_number=3, text="Page three."),
        ]
        chunks = chunk_hierarchical(pages, page_group_size=3, page_group_stride=2)
        page_groups = self._page_groups(chunks)
        first_group = page_groups[0]
        self.assertIn("Page one.", first_group.content)
        self.assertIn("Page two.", first_group.content)
        self.assertIn("Page three.", first_group.content)
        self.assertEqual(first_group.page_start, 1)
        self.assertEqual(first_group.page_end, 3)

    def test_page_group_sliding_window(self):
        pages = [PageText(page_number=i, text=f"Page {i}.") for i in range(1, 6)]
        chunks = chunk_hierarchical(pages, page_group_size=3, page_group_stride=2)
        page_groups = self._page_groups(chunks)
        self.assertGreaterEqual(len(page_groups), 2)

    def test_chunks_link_to_parent_page_group(self):
        pages = [
            PageText(page_number=1, text="Page one."),
            PageText(page_number=2, text="Page two."),
            PageText(page_number=3, text="Page three."),
        ]
        chunks = chunk_hierarchical(pages, page_group_size=3, page_group_stride=2)
        individual_chunks = self._chunks(chunks)
        for c in individual_chunks:
            if c.page_start <= 3:
                self.assertIsNotNone(c.page_group_index)

    def test_empty_pages_returns_empty_list(self):
        result = chunk_hierarchical([])
        self.assertEqual(result, [])

    def test_zero_overlap_works(self):
        pages = [PageText(page_number=1, text="A " * 4000)]
        chunks = self._chunks(chunk_hierarchical(pages, chunk_size=1000, overlap=0))
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c.content), 1010)

    def test_chunk_content_does_not_exceed_max_size_significantly(self):
        pages = [PageText(page_number=1, text="word " * 5000)]
        chunks = self._chunks(chunk_hierarchical(pages, chunk_size=1000, overlap=200))
        for c in chunks:
            self.assertLessEqual(len(c.content), 1050)
