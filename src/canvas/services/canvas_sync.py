from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable

import requests

from accounts.models import User
from canvas.canvas_service import CanvasOAuth2Service
from canvas.models import CanvasFileSync
from courses.models import Course
from rag.models import CourseMaterial, CourseMaterialBlob
from rag.forms import title_from_filename
from rag.tasks import index_course_material

logger = logging.getLogger(__name__)


class CanvasSyncService:
    """Service for syncing Canvas PDFs into RAG course materials.

    Handles downloading PDFs from Canvas, deduplicating by checksum,
    creating CourseMaterial records, and triggering indexing.
    """

    def __init__(
        self,
        canvas_service: CanvasOAuth2Service | None = None,
        download: Callable[[str], bytes] | None = None,
    ):
        self._canvas_service = canvas_service or CanvasOAuth2Service()
        self._download = download or self._default_download

    @staticmethod
    def _default_download(url: str) -> bytes:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def sync_course_pdfs(
        self,
        user: User,
        course: Course,
        canvas_file_ids: list[str],
    ) -> dict[str, int]:
        """
        Download selected Canvas PDFs and import them as CourseMaterials.

        Args:
            user: The teacher initiating the sync.
            course: The course to sync files into.
            canvas_file_ids: List of Canvas file IDs (strings) to download.

        Returns:
            dict with "synced" and "skipped" counts.
        """
        token = self._canvas_service.get_or_refresh_token(user)
        if not token:
            raise RuntimeError("Canvas token unavailable for this user.")

        assert course.canvas_course_id is not None
        canvas_files = self._canvas_service.get_course_files(
            course.canvas_course_id, token
        )

        synced = 0
        skipped = 0

        for cf in canvas_files:
            if cf.file_id not in canvas_file_ids:
                continue

            if not cf.filename.lower().endswith(".pdf"):
                skipped += 1
                continue

            if CanvasFileSync.objects.filter(
                course=course, canvas_file_id=cf.file_id
            ).exists():
                skipped += 1
                continue

            public_url = self._canvas_service.get_file_public_url(
                cf.file_id, token
            )
            if not public_url:
                logger.warning(
                    "No public URL for Canvas file %s, skipping", cf.file_id
                )
                skipped += 1
                continue

            try:
                pdf_data = self._download(public_url)
            except requests.RequestException:
                logger.exception("Failed to download Canvas file %s", cf.file_id)
                skipped += 1
                continue

            checksum = hashlib.sha256(pdf_data).hexdigest()

            if CourseMaterial.objects.filter(course=course, checksum=checksum).exists():
                skipped += 1
                continue

            try:
                material = CourseMaterial.objects.create(
                    course=course,
                    title=title_from_filename(cf.filename),
                    original_filename=cf.filename,
                    content_type="application/pdf",
                    size=len(pdf_data),
                    checksum=checksum,
                )
                CourseMaterialBlob.objects.create(material=material, data=pdf_data)

                CanvasFileSync.objects.create(
                    course=course,
                    canvas_file_id=cf.file_id,
                    display_name=cf.display_name or cf.filename,
                    filename=cf.filename,
                    size=cf.size,
                    checksum=checksum,
                    material=material,
                )

                index_course_material(
                    material_id=str(material.id),
                    course_id=str(course.id),
                )

                synced += 1
            except Exception:
                logger.exception(
                    "Failed to create CourseMaterial for Canvas file %s",
                    cf.file_id,
                )
                skipped += 1

        return {"synced": synced, "skipped": skipped}
