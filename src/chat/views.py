import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from courses.models import Course
from chat.models import Chat, ChatMessage
from chat.services import ChatService

logger = logging.getLogger(__name__)


def _check_chat_access(user, course):
    from django.core.exceptions import PermissionDenied

    if hasattr(user, "teacher_profile"):
        if not course.teachers.filter(id=user.teacher_profile.id).exists():
            raise PermissionDenied
    elif hasattr(user, "student_profile"):
        if not course.is_student_enrolled(user.student_profile):
            raise PermissionDenied
    elif hasattr(user, "teacher_assistant_profile"):
        if not course.is_teacher_assistant(user.teacher_assistant_profile):
            raise PermissionDenied
    else:
        raise PermissionDenied


@method_decorator(login_required, name="dispatch")
class ChatDetailView(View):
    """Course chat page — shows chat list sidebar and active chat."""

    def get(self, request: HttpRequest, course_id, chat_id=None):
        course = get_object_or_404(Course, id=course_id)
        _check_chat_access(request.user, course)

        chats = ChatService.get_user_chats(request.user, course)

        if chat_id:
            active_chat = get_object_or_404(Chat, id=chat_id, course=course)
            if active_chat.user != request.user or active_chat.is_deleted:
                from django.http import Http404
                raise Http404
        elif chats:
            active_chat = chats[0]
        else:
            active_chat = ChatService.start_chat(request.user, course)
            chats = [active_chat]

        chat_messages_list = active_chat.messages.order_by("timestamp").select_related("chat__course")

        return render(request, "chat/course_chat.html", {
            "chats": chats,
            "active_chat": active_chat,
            "course": course,
            "chat_messages": chat_messages_list,
            "stream_url": reverse("chat:stream", kwargs={
                "course_id": course_id, "chat_id": active_chat.id
            }),
        })


@method_decorator(login_required, name="dispatch")
class ChatCreateView(View):
    """Create a new empty chat for the course."""

    def post(self, request: HttpRequest, course_id):
        course = get_object_or_404(Course, id=course_id)
        _check_chat_access(request.user, course)
        chat = ChatService.create_chat(request.user, course)
        return redirect("chat:course_chat_detail", course_id=course_id, chat_id=chat.id)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_POST, name="dispatch")
@method_decorator(login_required, name="dispatch")
class ChatStreamView(View):
    """SSE streaming endpoint for course chat messages."""

    def post(self, request: HttpRequest, course_id, chat_id):
        course = get_object_or_404(Course, id=course_id)
        _check_chat_access(request.user, course)
        chat = get_object_or_404(Chat, id=chat_id, course=course, user=request.user, is_deleted=False)

        try:
            body = json.loads(request.body)
            content = body.get("content", "").strip()
        except (json.JSONDecodeError, AttributeError):
            return HttpResponse(status=400)

        if not content:
            return HttpResponse(status=400)

        def event_stream():
            try:
                yield from ChatService.process_message_stream(chat, content)
            except Exception as e:
                logger.error(f"Chat stream error: {e}", exc_info=True)
                yield f"event: error\ndata: Internal error\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
