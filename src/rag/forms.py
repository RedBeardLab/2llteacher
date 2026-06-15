import os
import re
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

MAX_PDF_UPLOAD_SIZE = 25 * 1024 * 1024
PDF_CONTENT_TYPE = "application/pdf"


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data: Any, initial: Any = None) -> list[Any]:
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file_data, initial) for file_data in data]
        return [single_file_clean(data, initial)]


def title_from_filename(filename: str | None) -> str:
    if not filename:
        return "Untitled PDF"

    basename = os.path.basename(filename)
    stem, _extension = os.path.splitext(basename)
    normalized = re.sub(r"\s+", " ", stem).strip()
    return normalized or basename or "Untitled PDF"


def validate_pdf_upload(uploaded_file: Any) -> None:
    filename = uploaded_file.name or ""
    content_type = uploaded_file.content_type or ""

    if not filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files can be uploaded.")

    if content_type != PDF_CONTENT_TYPE:
        raise ValidationError("Only PDF files can be uploaded.")

    if uploaded_file.size == 0:
        raise ValidationError("Uploaded PDFs cannot be empty.")

    if uploaded_file.size > MAX_PDF_UPLOAD_SIZE:
        raise ValidationError("PDF files must be 25 MB or smaller.")


class CourseMaterialUploadForm(forms.Form):
    pdf_files = MultipleFileField(
        allow_empty_file=True,
        widget=MultipleFileInput(
            attrs={
                "accept": ".pdf,application/pdf",
                "multiple": True,
                "class": "form-control",
            }
        ),
    )

    def clean_pdf_files(self) -> list[Any]:
        files = self.cleaned_data["pdf_files"]
        if not files:
            raise ValidationError("Select at least one PDF to upload.")

        for uploaded_file in files:
            validate_pdf_upload(uploaded_file)

        return files


class CourseMaterialTitleForm(forms.Form):
    title = forms.CharField(max_length=255, strip=True)
