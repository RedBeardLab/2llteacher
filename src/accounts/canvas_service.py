from dataclasses import dataclass
from typing import Any, Optional
import secrets
import logging

import requests
from django.conf import settings as django_settings
from django.http import HttpRequest
from django.db import transaction
from django.urls import reverse

from .models import User, Student, CanvasProfile

logger = logging.getLogger(__name__)


@dataclass
class CanvasTokenResult:
    success: bool
    access_token: str = ""
    refresh_token: str = ""
    error: Optional[str] = None


@dataclass
class CanvasUserInfo:
    canvas_user_id: str
    name: str
    email: str = ""
    login_id: str = ""


@dataclass
class CanvasCourseInfo:
    canvas_course_id: str
    name: str
    code: str


class CanvasOAuth2Service:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        settings_module: Any = None,
    ):
        self._session = session or requests.Session()
        self._settings = settings_module or django_settings

    def get_authorization_url(self, request: HttpRequest) -> str:
        state = secrets.token_urlsafe(32)
        request.session["canvas_oauth_state"] = state

        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        client_id = self._settings.CANVAS_CLIENT_ID
        redirect_uri = request.build_absolute_uri(
            reverse("accounts:canvas_callback")
        )
        scopes = getattr(self._settings, "CANVAS_OAUTH_SCOPES", "")

        params = (
            f"client_id={client_id}"
            f"&response_type=code"
            f"&state={state}"
            f"&redirect_uri={redirect_uri}"
        )
        if scopes:
            params += f"&scope={scopes}"
        return f"{base_url}/login/oauth2/auth?{params}"

    def verify_state(self, request: HttpRequest, state: str) -> bool:
        expected = request.session.pop("canvas_oauth_state", None)
        if not expected or not state:
            return False
        return secrets.compare_digest(expected, state)

    def exchange_code(self, code: str, redirect_uri: str) -> CanvasTokenResult:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            response = self._session.post(
                f"{base_url}/login/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self._settings.CANVAS_CLIENT_ID,
                    "client_secret": self._settings.CANVAS_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return CanvasTokenResult(
                success=True,
                access_token=data.get("access_token", ""),
                refresh_token=data.get("refresh_token", ""),
            )
        except requests.RequestException as e:
            logger.exception("Failed to exchange Canvas auth code")
            return CanvasTokenResult(success=False, error=str(e))

    def get_user_info(self, access_token: str) -> CanvasUserInfo:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            response = self._session.get(
                f"{base_url}/api/v1/users/self",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return CanvasUserInfo(
                canvas_user_id=str(data.get("id", "")),
                name=data.get("name", ""),
                email=data.get("email", ""),
                login_id=data.get("login_id", ""),
            )
        except requests.RequestException:
            logger.exception("Failed to fetch Canvas user info")
            raise

    def get_teacher_courses(self, access_token: str) -> list[CanvasCourseInfo]:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            params: dict[str, str | int] = {
                "enrollment_type": "teacher",
                "enrollment_state": "active",
                "per_page": 100,
                "include[]": "term",
            }
            response = self._session.get(
                f"{base_url}/api/v1/courses",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return [
                CanvasCourseInfo(
                    canvas_course_id=str(course["id"]),
                    name=course.get("name", ""),
                    code=course.get("course_code", ""),
                )
                for course in data
                if course.get("name") or course.get("course_code")
            ]
        except requests.RequestException:
            logger.exception("Failed to fetch Canvas courses")
            return []

    def get_teacher_courses_for_user(self, user: User) -> list[CanvasCourseInfo]:
        try:
            profile = user.canvas_profile
            return self.get_teacher_courses(profile.access_token)
        except CanvasProfile.DoesNotExist:
            return []

    @transaction.atomic
    def get_or_create_user(self, info: CanvasUserInfo) -> tuple[User, bool]:
        try:
            profile = CanvasProfile.objects.select_related("user").get(
                canvas_user_id=info.canvas_user_id
            )
            return profile.user, False
        except CanvasProfile.DoesNotExist:
            pass

        if info.email:
            try:
                user = User.objects.get(email=info.email)
                CanvasProfile.objects.create(
                    user=user,
                    canvas_user_id=info.canvas_user_id,
                )
                return user, False
            except User.DoesNotExist:
                pass

        name_parts = info.name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        email = info.email
        if not email and info.login_id:
            email = f"{info.login_id}@uw.edu"

        username = email or f"canvas_{info.canvas_user_id}"
        user = User.objects.create_user(
            username=username,
            email=email or "",
            first_name=first_name,
            last_name=last_name,
        )
        user.is_email_verified = True
        user.set_unusable_password()
        user.save()

        Student.objects.create(user=user)

        CanvasProfile.objects.create(
            user=user,
            canvas_user_id=info.canvas_user_id,
        )

        return user, True
