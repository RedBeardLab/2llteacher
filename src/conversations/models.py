import uuid
from django.db import models
from django.core.validators import MinLengthValidator
from django.utils import timezone


class Conversation(models.Model):
    """AI conversation between user and LLM for a specific section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="conversations"
    )
    section = models.ForeignKey(
        "homeworks.Section", on_delete=models.CASCADE, related_name="conversations"
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations_conversation"
        ordering = ["-created_at"]

    def __str__(self):
        user_type = "Teacher" if self.is_teacher_test else "Student"
        return f"{user_type} conversation {self.id} - {self.user.username} on {self.section}"

    def soft_delete(self):
        """Soft delete the conversation."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    @property
    def message_count(self):
        return self.messages.count()

    @property
    def is_teacher_test(self):
        """Check if this is a teacher test conversation."""
        return hasattr(self.user, "teacher_profile")

    @property
    def is_student_conversation(self):
        """Check if this is a student conversation."""
        return hasattr(self.user, "student_profile")


class Message(models.Model):
    """Individual message in a conversation."""

    # Common message types (for reference, but not enforced)
    MESSAGE_TYPE_STUDENT = "student"
    MESSAGE_TYPE_AI = "ai"
    MESSAGE_TYPE_R_CODE = "code"
    MESSAGE_TYPE_FILE_UPLOAD = "file_upload"
    MESSAGE_TYPE_CODE_EXECUTION = "code_execution"
    MESSAGE_TYPE_SYSTEM = "system"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField(validators=[MinLengthValidator(1)])
    message_type = models.CharField(
        max_length=50,
        help_text="Type of message (e.g., 'student', 'ai', 'r_code', 'file_upload', etc.)",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_message"
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.message_type} message at {self.timestamp}"

    @property
    def is_from_student(self):
        """Check if this is a student message."""
        return self.message_type in [
            self.MESSAGE_TYPE_STUDENT,
            self.MESSAGE_TYPE_R_CODE,
            self.MESSAGE_TYPE_FILE_UPLOAD,
            self.MESSAGE_TYPE_CODE_EXECUTION,
        ]

    @property
    def is_from_ai(self):
        """Check if this is an AI response."""
        return self.message_type == self.MESSAGE_TYPE_AI

    @property
    def is_system_message(self):
        """Check if this is a system message."""
        return self.message_type == self.MESSAGE_TYPE_SYSTEM


class Submission(models.Model):
    """Student submission for a specific section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation, on_delete=models.CASCADE, related_name="submission"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_submission"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Submission by {self.conversation.user.username} for {self.conversation.section}"

    @property
    def section(self):
        """Get the section through the conversation."""
        return self.conversation.section

    @property
    def student(self):
        """Get the student through the conversation."""
        return self.conversation.user.student_profile

    def clean(self):
        """Ensure only one submission per student per section."""
        from django.core.exceptions import ValidationError

        # Check if another submission exists for the same student and section
        existing_submission = Submission.objects.filter(
            conversation__user=self.conversation.user,
            conversation__section=self.conversation.section,
        ).exclude(id=self.id)

        if existing_submission.exists():
            raise ValidationError("Student already has a submission for this section.")


class PasteEvent(models.Model):
    """Record of paste detection events for review."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_message_before_paste = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        related_name="paste_events_after",
        null=True,
        blank=True,
        help_text="Last message sent before this paste event occurred",
    )
    pasted_content = models.TextField(help_text="Full content that was pasted")
    word_count = models.IntegerField(help_text="Number of words in pasted content")
    content_length = models.IntegerField(help_text="Character length of pasted content")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_paste_event"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Paste event - {self.word_count} words at {self.timestamp}"

    @property
    def conversation(self):
        """Get the conversation through the last message."""
        if self.last_message_before_paste:
            return self.last_message_before_paste.conversation
        return None


class RapidTextGrowthEvent(models.Model):
    """Record of rapid text growth detection events for review."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_message_before_event = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        related_name="rapid_text_growth_events_after",
        null=True,
        blank=True,
        help_text="Last message sent before this rapid text growth event occurred",
    )
    added_text = models.TextField(
        help_text="Text that was added during the 100ms window"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_rapid_text_growth_event"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Rapid text growth - {len(self.added_text)} chars at {self.timestamp}"

    @property
    def conversation(self):
        """Get the conversation through the last message."""
        if self.last_message_before_event:
            return self.last_message_before_event.conversation
        return None
