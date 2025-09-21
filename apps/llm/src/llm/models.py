import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class LLMConfig(models.Model):
    """Configuration for LLM integration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
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

    def __str__(self):
        return f"{self.name} ({self.model_name})"

    def save(self, *args, **kwargs):
        """Ensure only one default config exists."""
        if self.is_default:
            LLMConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
