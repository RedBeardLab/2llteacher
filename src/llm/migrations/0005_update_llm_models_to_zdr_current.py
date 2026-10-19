# Generated to refresh LLM model names to current ZDR-capable OpenRouter models.

from django.db import migrations


# Maps outdated / removed / deprecated model names to their current,
# ZDR-capable, non-free OpenRouter replacement (see config_form.html).
MODEL_MAPPING = {
    # Nano / ultra low cost
    "openai/gpt-5-nano": "openai/gpt-6-luna",
    "openai/gpt-4.1-nano": "openai/gpt-6-luna",
    "openai/gpt-4o-mini": "openai/gpt-6-luna",
    "openai/gpt-3.5-turbo": "openai/gpt-6-luna",
    "openai/gpt-4": "openai/gpt-6-luna",
    # Reasoning / mini
    "openai/gpt-5-mini": "openai/gpt-6-luna-pro",
    "openai/o3-mini-high": "openai/gpt-6-luna-pro",
    "openai/o4-mini": "openai/gpt-6-luna-pro",
    "openai/gpt-4.1-mini": "openai/gpt-6-luna-pro",
    # Anthropic cheap tier
    "anthropic/claude-3-haiku": "anthropic/claude-haiku-5.5",
    "anthropic/claude-3.5-haiku": "anthropic/claude-haiku-5.5",
    # Google
    "google/gemini-2.0-flash-exp:free": "google/gemini-3.5-flash-lite",
    "google/gemini-2.0-flash-lite-001": "google/gemini-3.5-flash-lite",
    "google/gemini-2.5-flash-lite": "google/gemini-3.5-flash-lite",
    "google/gemini-2.5-flash": "google/gemini-3.8-flash",
    "google/gemini-2.5-pro": "google/gemini-4-argon",
    # Flagship general / chat
    "openai/gpt-5": "openai/gpt-6.1-sol",
    "openai/gpt-5-chat": "openai/gpt-6.1-sol",
    "openai/gpt-4o": "openai/gpt-6.1-sol",
    # Code
    "openai/gpt-5-codex": "openai/gpt-6.1-sol-pro",
    # Specialized search
    "openai/gpt-4o-mini-search-preview": "perplexity/sonar-pro-search",
    # Premium Claude
    "anthropic/claude-3.7-sonnet": "anthropic/claude-sonnet-5.5",
    "anthropic/claude-sonnet-4": "anthropic/claude-sonnet-5.5",
    "anthropic/claude-opus-4": "anthropic/claude-opus-5.5",
    "anthropic/claude-opus-4.1": "anthropic/claude-opus-5.5",
    # Premium reasoning
    "openai/o3": "openai/gpt-6.1-sol-pro",
    "openai/o3-pro": "openai/gpt-6-astra-pro",
    "openai/o1-pro": "openai/gpt-6-astra-pro",
}

# Best-effort inverse for rollback. Many-to-one mappings collapse to the
# first/representative source model.
REVERSE_MAPPING = {}
for _old, _new in MODEL_MAPPING.items():
    REVERSE_MAPPING.setdefault(_new, _old)

# NOTE: "openai/gpt-4o-audio-preview" is intentionally NOT remapped.
# OpenRouter offers no ZDR-capable audio endpoint, so there is no safe
# automatic replacement. Such configs are left untouched and will require
# manual review.


def _apply_mapping(apps, mapping):
    updated = 0
    for model in ("LLMConfig", "GlobalLLMDefault"):
        Model = apps.get_model("llm", model)
        for old_name, new_name in mapping.items():
            count = Model.objects.filter(model_name=old_name).update(
                model_name=new_name
            )
            if count:
                print(f"{model}: {old_name} -> {new_name} ({count})")
                updated += count
    print(f"Total LLM configs updated: {updated}")


def forwards(apps, schema_editor):
    _apply_mapping(apps, MODEL_MAPPING)


def backwards(apps, schema_editor):
    _apply_mapping(apps, REVERSE_MAPPING)


class Migration(migrations.Migration):

    dependencies = [
        ("llm", "0004_globalllmdefault_llmconfig_course_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
