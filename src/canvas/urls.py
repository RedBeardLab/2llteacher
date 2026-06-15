from django.urls import path
from . import views

app_name = "canvas"

urlpatterns = [
    path("login/", views.CanvasLoginView.as_view(), name="canvas_login"),
    path("callback/", views.CanvasCallbackView.as_view(), name="canvas_callback"),
    path(
        "<uuid:course_id>/sync/",
        views.CanvasMaterialSyncView.as_view(),
        name="material-sync",
    ),
]
