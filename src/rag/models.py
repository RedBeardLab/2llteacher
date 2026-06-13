import uuid

from django.db import models


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


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
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    error_message = models.TextField(blank=True, default="")
    pages = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rag_course_material"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course", "-created_at"]),
            models.Index(fields=["checksum"]),
            models.Index(fields=["processing_status"]),
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


class CourseMaterialChunk(models.Model):
    """A chunk of text extracted from a course material PDF."""

    class Level(models.TextChoices):
        PAGE_GROUP = "page_group", "Page Group"
        CHUNK = "chunk", "Chunk"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(
        CourseMaterial, on_delete=models.CASCADE, related_name="chunks"
    )
    level = models.CharField(max_length=10, choices=Level.choices)
    chunk_index = models.IntegerField()
    page_group_index = models.IntegerField(null=True, blank=True)
    content = models.TextField()
    page_start = models.IntegerField()
    page_end = models.IntegerField()
    embedding = models.BinaryField(null=True, blank=True)
    token_count = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rag_course_material_chunk"
        ordering = ["material", "level", "chunk_index"]
        unique_together = [["material", "level", "chunk_index"]]
        indexes = [
            models.Index(fields=["material", "level"]),
        ]

    def __str__(self) -> str:
        return f"{self.level} #{self.chunk_index} of {self.material_id}"
