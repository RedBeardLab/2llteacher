"""
URL patterns for the homeworks app.
"""

from django.urls import path

from . import views

app_name = "homeworks"

urlpatterns = [
    path("", views.HomeworkListView.as_view(), name="list"),
    path("matrix/", views.HomeworkMatrixView.as_view(), name="matrix"),
    path("matrix/export/", views.HomeworkMatrixExportView.as_view(), name="matrix_export"),
    path("<uuid:homework_id>/", views.HomeworkDetailView.as_view(), name="detail"),
    path("<uuid:homework_id>/edit/", views.HomeworkEditView.as_view(), name="edit"),
    path(
        "<uuid:homework_id>/submissions/",
        views.HomeworkSubmissionsView.as_view(),
        name="submissions",
    ),
    path(
        "<uuid:homework_id>/sections/<uuid:section_id>/",
        views.SectionDetailView.as_view(),
        name="section_detail",
    ),
]
