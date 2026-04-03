"""
URL patterns for the courses app.
"""

from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    path("", views.CourseListView.as_view(), name="list"),
    path("create/", views.CourseCreateView.as_view(), name="create"),
    path("<uuid:course_id>/", views.CourseDetailView.as_view(), name="detail"),
    path("<uuid:course_id>/enroll/", views.CourseEnrollView.as_view(), name="enroll"),
    path(
        "<uuid:course_id>/homework/create/",
        views.CourseHomeworkCreateView.as_view(),
        name="homework-create",
    ),
    path(
        "<uuid:course_id>/ta/assign/",
        views.CourseTAAssignView.as_view(),
        name="ta-assign",
    ),
    path(
        "<uuid:course_id>/ta/<uuid:ta_id>/remove/",
        views.CourseTARemoveView.as_view(),
        name="ta-remove",
    ),
    path(
        "<uuid:course_id>/matrix/",
        views.CourseMatrixView.as_view(),
        name="matrix",
    ),
    path(
        "<uuid:course_id>/matrix/export/",
        views.CourseMatrixExportView.as_view(),
        name="matrix-export",
    ),
]
