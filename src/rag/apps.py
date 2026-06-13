from django.apps import AppConfig


class RagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rag"

    def ready(self) -> None:
        from .sqlite_vector_extension import register_sqlite_vector_loader

        register_sqlite_vector_loader()
