from django.urls import path

from . import views

app_name = "materials"

urlpatterns = [
    path(
        "<uuid:material_id>/pdf/<str:checksum>.pdf",
        views.CourseMaterialPdfView.as_view(),
        name="pdf",
    ),
]
