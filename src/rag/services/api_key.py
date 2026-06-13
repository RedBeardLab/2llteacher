from llm.models import LLMConfig, GlobalLLMDefault


def resolve_embedding_api_key(course_id: str) -> str:
    config = (
        LLMConfig.objects.filter(course_id=course_id, is_active=True)
        .exclude(api_key="")
        .first()
    )
    if config and config.api_key:
        return config.api_key
    default = (
        GlobalLLMDefault.objects.filter(is_active=True).exclude(api_key="").first()
    )
    if default and default.api_key:
        return default.api_key
    return ""
