from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("course/<uuid:course_id>/", views.ChatDetailView.as_view(), name="course_chat"),
    path("course/<uuid:course_id>/new/", views.ChatCreateView.as_view(), name="chat_create"),
    path("course/<uuid:course_id>/<uuid:chat_id>/", views.ChatDetailView.as_view(), name="course_chat_detail"),
    path("course/<uuid:course_id>/<uuid:chat_id>/stream/", views.ChatStreamView.as_view(), name="stream"),
]
