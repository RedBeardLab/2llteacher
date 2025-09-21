"""
URL patterns for the LLM app.
"""

from django.urls import path

from . import views

app_name = "llm"

urlpatterns = [
    # LLM Configuration management
    path("", views.LLMConfigListView.as_view(), name="config-list"),
    path("create/", views.LLMConfigCreateView.as_view(), name="config-create"),
    path(
        "<uuid:config_id>/", views.LLMConfigDetailView.as_view(), name="config-detail"
    ),
    path(
        "<uuid:config_id>/edit/", views.LLMConfigEditView.as_view(), name="config-edit"
    ),
    path(
        "<uuid:config_id>/delete/",
        views.LLMConfigDeleteView.as_view(),
        name="config-delete",
    ),
    path(
        "<uuid:config_id>/test/", views.LLMConfigTestView.as_view(), name="config-test"
    ),
    # API endpoints for other apps
    path("api/generate/", views.LLMGenerateAPIView.as_view(), name="api-generate"),
    path("api/configs/", views.LLMConfigsAPIView.as_view(), name="api-configs"),
]
