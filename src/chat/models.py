import uuid

from django.db import models
from django.core.validators import MinLengthValidator


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="chats"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="course_chats"
    )
    title = models.CharField(max_length=200, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_chat"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Chat {self.user.username} - {self.course.name}"


class ChatMessage(models.Model):
    MESSAGE_TYPE_STUDENT = "student"
    MESSAGE_TYPE_AI = "ai"
    MESSAGE_TYPE_SYSTEM = "system"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField(validators=[MinLengthValidator(1)])
    message_type = models.CharField(max_length=50)
    tool_call_id = models.CharField(max_length=100, null=True, blank=True)
    tool_call_arguments = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_chat_message"
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.message_type} message at {self.timestamp}"


class ChatMessageContext(models.Model):
    message = models.ForeignKey(
        ChatMessage, on_delete=models.CASCADE, related_name="contexts"
    )
    chunk = models.ForeignKey(
        "rag.CourseMaterialChunk",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    material_title = models.CharField(max_length=255)
    page_start = models.IntegerField()
    page_end = models.IntegerField()
    content = models.TextField(help_text="The chunk text used as context")
    score = models.FloatField(help_text="Cosine similarity score (lower = closer)")
    query = models.TextField(help_text="The search query that triggered this retrieval")

    class Meta:
        db_table = "chat_chat_message_context"
        ordering = ["score"]

    def __str__(self):
        return f'Context: "{self.material_title}" pages {self.page_start}-{self.page_end} ({self.score:.3f})'
