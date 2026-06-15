import uuid

from django.db import models


class CanvasProfile(models.Model):
    """Stores Canvas LMS OAuth2 credentials linked to a User."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="canvas_profile"
    )
    canvas_user_id = models.CharField(max_length=64, unique=True)
    access_token = models.CharField(max_length=255, blank=True)
    refresh_token = models.CharField(max_length=255, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "canvas_canvasprofile"

    def __str__(self):
        return f"Canvas({self.canvas_user_id}) -> {self.user.username}"


class CanvasFileSync(models.Model):
    """Tracks which Canvas files have been synced to the RAG system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="canvas_file_syncs"
    )
    canvas_file_id = models.CharField(max_length=64)
    display_name = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64)
    material = models.OneToOneField(
        "rag.CourseMaterial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canvas_sync",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "canvas_canvasfilesync"
        unique_together = [["course", "canvas_file_id"]]

    def __str__(self):
        return f"{self.display_name} -> {self.course.code}"
