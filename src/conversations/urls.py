"""
URL patterns for the conversations app.
"""

from django.urls import path

from . import views

app_name = "conversations"

urlpatterns = [
    path(
        "section/<uuid:section_id>/start/",
        views.ConversationStartView.as_view(),
        name="start",
    ),
    path(
        "<uuid:conversation_id>/", views.ConversationDetailView.as_view(), name="detail"
    ),
    path(
        "<uuid:conversation_id>/send/",
        views.MessageSendView.as_view(),
        name="send_message",
    ),
    path(
        "<uuid:conversation_id>/submit/",
        views.ConversationSubmitView.as_view(),
        name="submit_conversation",
    ),
    path(
        "<uuid:conversation_id>/delete-and-restart/",
        views.ConversationDeleteAndRestartView.as_view(),
        name="delete_and_restart",
    ),
    # API endpoints for real-time chat
    path(
        "api/<uuid:conversation_id>/stream/",
        views.ConversationStreamView.as_view(),
        name="api_stream",
    ),
    path(
        "api/<uuid:conversation_id>/log-paste/",
        views.PasteLogView.as_view(),
        name="api_log_paste",
    ),
]
