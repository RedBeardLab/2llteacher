import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class GlobalLLMDefault(models.Model):
    """Global default LLM configuration template for new courses."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    model_name = models.CharField(
        max_length=100, help_text="LLM model to use (e.g., 'gpt-4', 'gpt-3.5-turbo')"
    )
    api_key = models.CharField(max_length=255, help_text="API key for LLM service")
    base_prompt = models.TextField(help_text="Base prompt template for AI tutor")
    temperature = models.FloatField(
        default=0.7, validators=[MinValueValidator(0.0), MaxValueValidator(2.0)]
    )
    max_completion_tokens = models.PositiveIntegerField(default=1000)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_global_default"

    def __str__(self):
        return f"Global Default: {self.name} ({self.model_name})"

    def create_course_config(self, course):
        """Create a course-specific config from this global default."""
        return LLMConfig.objects.create(
            course=course,
            name=self.name,
            model_name=self.model_name,
            api_key=self.api_key,
            base_prompt=self.base_prompt,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
            is_default=True,
            is_active=self.is_active,
        )


class LLMConfig(models.Model):
    """Configuration for LLM integration, scoped to a course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="llm_configs",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    model_name = models.CharField(
        max_length=100, help_text="LLM model to use (e.g., 'gpt-4', 'gpt-3.5-turbo')"
    )
    api_key = models.CharField(max_length=255, help_text="API key for LLM service")
    base_prompt = models.TextField(help_text="Base prompt template for AI tutor")
    temperature = models.FloatField(
        default=0.7, validators=[MinValueValidator(0.0), MaxValueValidator(2.0)]
    )
    max_completion_tokens = models.PositiveIntegerField(default=1000)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_config"
        unique_together = ["course", "name"]

    def __str__(self):
        course_name = self.course.name if self.course else "No Course"
        return f"{self.name} ({self.model_name}) - {course_name}"

    def save(self, *args, **kwargs):
        """Ensure only one default config exists per course."""
        if self.is_default:
            LLMConfig.objects.filter(course=self.course, is_default=True).exclude(
                id=self.id
            ).update(is_default=False)
        super().save(*args, **kwargs)
