import uuid

from django.db import models


class CourseMaterial(models.Model):
    """PDF material uploaded for a course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="materials"
    )
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default="application/pdf")
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_course_materials",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rag_course_material"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course", "-created_at"]),
            models.Index(fields=["checksum"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.course.code})"


class CourseMaterialBlob(models.Model):
    """Blob storage for course material PDFs."""

    material = models.OneToOneField(
        CourseMaterial,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="blob",
    )
    data = models.BinaryField()

    class Meta:
        db_table = "rag_course_material_blob"

    def __str__(self) -> str:
        return f"Blob for {self.material_id}"
