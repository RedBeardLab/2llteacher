import fitz


class PageText:
    def __init__(self, page_number: int, text: str) -> None:
        self.page_number = page_number
        self.text = text


def extract_pages(pdf_data: bytes) -> list[PageText]:
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    pages: list[PageText] = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text().strip()
        if text:
            pages.append(PageText(page_number=page_num + 1, text=text))
    doc.close()
    return pages
