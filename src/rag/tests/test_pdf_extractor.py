import fitz
from django.test import SimpleTestCase

from rag.services.pdf_extractor import PageText, extract_pages


class ExtractPagesTests(SimpleTestCase):
    def make_pdf(self, pages: list[str]) -> bytes:
        doc = fitz.open()
        for text in pages:
            page = doc.new_page()
            page.insert_text(fitz.Point(72, 72), text, fontsize=12)
        return doc.tobytes()

    def test_extracts_text_from_single_page(self):
        pdf_data = self.make_pdf(["Hello world"])
        result = extract_pages(pdf_data)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], PageText)
        self.assertEqual(result[0].page_number, 1)
        self.assertIn("Hello world", result[0].text)

    def test_extracts_text_from_multiple_pages(self):
        pdf_data = self.make_pdf(["Page one content", "Page two content"])
        result = extract_pages(pdf_data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].page_number, 1)
        self.assertIn("Page one", result[0].text)
        self.assertEqual(result[1].page_number, 2)
        self.assertIn("Page two", result[1].text)

    def test_page_numbers_are_one_based(self):
        pdf_data = self.make_pdf(["First", "Second", "Third"])
        result = extract_pages(pdf_data)
        self.assertEqual([p.page_number for p in result], [1, 2, 3])

    def test_returns_empty_list_for_pdf_with_no_text(self):
        doc = fitz.open()
        doc.new_page()
        pdf_data = doc.tobytes()
        doc.close()
        result = extract_pages(pdf_data)
        self.assertEqual(result, [])

    def test_preserves_text_order_across_pages(self):
        pdf_data = self.make_pdf(["Alpha", "Beta", "Gamma"])
        result = extract_pages(pdf_data)
        texts = [p.text for p in result]
        self.assertEqual(texts, ["Alpha", "Beta", "Gamma"])

    def test_handles_non_pdf_bytes_gracefully(self):
        with self.assertRaises(Exception):
            extract_pages(b"not a pdf")
