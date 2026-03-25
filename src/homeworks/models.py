import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class HomeworkType(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class Homework(models.Model):
    """Homework assignment with multiple sections."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(
        "accounts.Teacher", on_delete=models.CASCADE, related_name="homeworks_created"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="homeworks"
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Required before publishing. Drafts may leave this blank.",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically hide from students after this date. Leave blank to never auto-hide.",
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text="Source of truth for student visibility. True means students cannot access.",
    )
    # Display-only type — never use for access control, use is_hidden instead.
    # draft: not yet published; published: visible to students; hidden: published but manually hidden.
    homework_type = models.CharField(
        max_length=20,
        choices=HomeworkType.choices,
        default=HomeworkType.PUBLISHED,
        help_text="Display label only. is_hidden is the access control source of truth.",
    )
    publish_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Auto-publish this draft at the given datetime.",
    )
    llm_config = models.ForeignKey(
        "llm.LLMConfig", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homeworks_homework"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def section_count(self):
        return self.sections.count()

    @property
    def is_overdue(self):
        return self.due_date is not None and timezone.now() > self.due_date

    @property
    def is_expired(self) -> bool:
        """True if the auto-expiry date has passed."""
        return self.expires_at is not None and timezone.now() > self.expires_at

    @property
    def is_draft(self) -> bool:
        """True when the homework has never been published (display label only)."""
        return self.homework_type == HomeworkType.DRAFT

    @property
    def is_accessible_to_students(self) -> bool:
        """False if the teacher has hidden it or the expiry date has passed.
        is_hidden is the single source of truth — this never reads homework_type."""
        if self.is_hidden:
            return False
        if self.is_expired:
            return False
        return True

    @property
    def should_auto_publish(self) -> bool:
        """True when a draft has a past publish_at and should be auto-published."""
        return (
            self.homework_type == HomeworkType.DRAFT
            and self.publish_at is not None
            and timezone.now() >= self.publish_at
        )


class Section(models.Model):
    """Individual section within a homework assignment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    homework = models.ForeignKey(
        Homework, on_delete=models.CASCADE, related_name="sections"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    solution = models.OneToOneField(
        "SectionSolution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="section",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homeworks_section"
        ordering = ["order"]
        unique_together = ["homework", "order"]

    def __str__(self):
        return f"{self.homework.title} - Section {self.order}: {self.title}"

    def clean(self):
        """Validate section data."""
        from django.core.exceptions import ValidationError

        # Ensure order is within homework's section limit
        if self.homework and self.order > 20:
            raise ValidationError("Maximum 20 sections allowed per homework.")

        # Ensure order is unique within homework
        if self.homework:
            existing_sections = Section.objects.filter(
                homework=self.homework, order=self.order
            ).exclude(id=self.id)

            if existing_sections.exists():
                raise ValidationError(
                    f"Section with order {self.order} already exists."
                )


class SectionSolution(models.Model):
    """Teacher-provided solution for a section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homeworks_section_solution"

    def __str__(self):
        if hasattr(self, "section") and self.section:
            return f"Solution for {self.section}"
        return f"Solution {self.id}"
