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
]
