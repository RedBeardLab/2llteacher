from dataclasses import dataclass
from typing import Optional, cast
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from accounts.models import User
from llteacher.permissions.decorators import teacher_required, TeacherRequest
from .canvas_service import CanvasOAuth2Service
from .services.canvas_sync import CanvasSyncService
from courses.models import Course

logger = logging.getLogger(__name__)


@dataclass
class CanvasCallbackError:
    error: str


CanvasCallbackResult = Optional[CanvasCallbackError]


class CanvasLoginView(View):
    """Initiate the Canvas OAuth2 login flow."""

    service_factory = CanvasOAuth2Service

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = self.service_factory()

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            return redirect("/")

        if not CanvasOAuth2Service.is_canvas_configured():
            messages.error(
                request,
                "Canvas login is not configured. Please use email/password instead.",
            )
            return redirect("accounts:login")

        auth_url = self._service.get_authorization_url(request)
        return redirect(auth_url)


class CanvasCallbackView(View):
    """Handle the OAuth2 callback from Canvas."""

    service_factory = CanvasOAuth2Service

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = self.service_factory()

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            messages.info(request, "You are already logged in.")
            return redirect("/")

        result = self._process_callback(request)

        if result is not None:
            messages.error(request, result.error)
            return redirect("accounts:login")

        return redirect("/")

    def _process_callback(self, request: HttpRequest) -> CanvasCallbackResult:
        code = request.GET.get("code", "")
        state = request.GET.get("state", "")

        if not self._service.verify_state(request, state):
            logger.warning(
                "Canvas OAuth2 state verification failed. "
                "state_param=%s session_has_key=%s session_keys=%s",
                state,
                "canvas_oauth_state" in request.session,
                list(request.session.keys()),
            )
            return CanvasCallbackError(error="Authentication failed. Please try again.")

        redirect_uri = request.build_absolute_uri(reverse("canvas:canvas_callback"))

        token_result = self._service.exchange_code(code, redirect_uri)
        if not token_result.success:
            logger.error("Canvas token exchange failed: %s", token_result.error)
            return CanvasCallbackError(
                error="Failed to authenticate with Canvas. Please try again."
            )

        try:
            user_info = self._service.get_user_info(token_result.access_token)
        except Exception:
            logger.exception("Failed to fetch Canvas user info")
            return CanvasCallbackError(
                error="Could not retrieve your account information from Canvas. Please try again."
            )

        user, _created = self._service.get_or_create_user(
            user_info,
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token,
            expires_in=token_result.expires_in,
        )

        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)

        return None


class CanvasMaterialSyncView(View):
    """Sync selected Canvas PDFs into the RAG system."""

    sync_service_factory = CanvasSyncService

    @method_decorator(login_required)
    @method_decorator(teacher_required)
    def post(self, request: TeacherRequest, course_id: str) -> HttpResponse:
        course = get_object_or_404(Course, id=course_id)

        if not course.canvas_course_id:
            messages.error(request, "This course is not linked to a Canvas course.")
            return redirect("courses:detail", course_id=course.id)

        canvas_file_ids = request.POST.getlist("canvas_file_ids")
        if not canvas_file_ids:
            messages.info(request, "No files selected.")
            return redirect("courses:detail", course_id=course.id)

        service = self.sync_service_factory()
        result = service.sync_course_pdfs(
            cast(User, request.user), course, canvas_file_ids
        )

        messages.success(
            request,
            f"Imported {result['synced']} file(s) from Canvas. "
            f"{result['skipped']} skipped (already imported).",
        )

        return redirect("courses:detail", course_id=course.id)
