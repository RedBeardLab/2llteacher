import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    """Custom user model with UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_email_verified = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_user"


class Teacher(models.Model):
    """Teacher profile with one-to-one relationship to User."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="teacher_profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_teacher"

    def __str__(self):
        return f"Teacher: {self.user.username}"


class Student(models.Model):
    """Student profile with one-to-one relationship to User."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_student"

    def __str__(self):
        return f"Student: {self.user.username}"


class EmailVerification(models.Model):
    """Email verification tokens for user registration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="email_verifications"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "accounts_email_verification"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        """Set expiration date to 7 days from creation if not set."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self) -> bool:
        """Check if the verification token has expired."""
        return timezone.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the token is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired()

    def __str__(self):
        return f"Email verification for {self.user.username} - {'Used' if self.is_used else 'Active'}"
