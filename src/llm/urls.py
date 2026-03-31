"""
URL patterns for the LLM app.
"""

from django.urls import path

from . import views

app_name = "llm"

urlpatterns = [
    path(
        "course/<uuid:course_id>/",
        views.LLMConfigListView.as_view(),
        name="config-list",
    ),
    path(
        "course/<uuid:course_id>/create/",
        views.LLMConfigCreateView.as_view(),
        name="config-create",
    ),
    path(
        "course/<uuid:course_id>/<uuid:config_id>/",
        views.LLMConfigDetailView.as_view(),
        name="config-detail",
    ),
    path(
        "course/<uuid:course_id>/<uuid:config_id>/edit/",
        views.LLMConfigEditView.as_view(),
        name="config-edit",
    ),
    path(
        "course/<uuid:course_id>/<uuid:config_id>/delete/",
        views.LLMConfigDeleteView.as_view(),
        name="config-delete",
    ),
    path(
        "course/<uuid:course_id>/<uuid:config_id>/test/",
        views.LLMConfigTestView.as_view(),
        name="config-test",
    ),
    path(
        "course/<uuid:course_id>/<uuid:config_id>/clone/",
        views.LLMConfigCloneView.as_view(),
        name="config-clone",
    ),
    path("api/generate/", views.LLMGenerateAPIView.as_view(), name="api-generate"),
    path("api/configs/", views.LLMConfigsAPIView.as_view(), name="api-configs"),
]
