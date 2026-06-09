from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime, timedelta
import secrets
import logging

import requests
from django.conf import settings as django_settings
from django.http import HttpRequest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import User, Student, CanvasProfile

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_EXPIRY_SECONDS = 3600


@dataclass
class CanvasTokenResult:
    success: bool
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0
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


@dataclass
class CanvasModuleItem:
    item_id: str
    title: str
    type: str
    url: str | None = None
    page_url: str | None = None


@dataclass
class CanvasModule:
    module_id: str
    name: str
    items: list[CanvasModuleItem]


@dataclass
class CanvasFile:
    file_id: str
    display_name: str
    filename: str
    url: str | None = None
    size: int = 0


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
                expires_in=data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS),
            )
        except requests.RequestException as e:
            logger.exception("Failed to exchange Canvas auth code")
            return CanvasTokenResult(success=False, error=str(e))

    def refresh_access_token(self, refresh_token: str) -> CanvasTokenResult:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            response = self._session.post(
                f"{base_url}/login/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._settings.CANVAS_CLIENT_ID,
                    "client_secret": self._settings.CANVAS_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return CanvasTokenResult(
                success=True,
                access_token=data.get("access_token", ""),
                expires_in=data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS),
            )
        except requests.RequestException as e:
            logger.exception("Failed to refresh Canvas access token")
            return CanvasTokenResult(success=False, error=str(e))

    def get_or_refresh_token(self, user: User) -> str | None:
        try:
            profile = user.canvas_profile
        except CanvasProfile.DoesNotExist:
            return None

        if not profile.access_token:
            return None

        if (
            profile.token_expires_at
            and timezone.now() < profile.token_expires_at
        ):
            return profile.access_token

        if not profile.refresh_token:
            return None

        result = self.refresh_access_token(profile.refresh_token)
        if not result.success:
            logger.error("Failed to refresh Canvas token for user %s", user.id)
            return None

        profile.access_token = result.access_token
        profile.token_expires_at = timezone.now() + timedelta(
            seconds=result.expires_in or DEFAULT_TOKEN_EXPIRY_SECONDS
        )
        profile.save(update_fields=["access_token", "token_expires_at"])

        return profile.access_token

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
            response = self._session.get(
                f"{base_url}/api/v1/courses",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "enrollment_type": "teacher",
                    "enrollment_state": "active",
                    "per_page": "100",
                    "include[]": "term",
                },
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
        token = self.get_or_refresh_token(user)
        if not token:
            return []
        return self.get_teacher_courses(token)

    def get_course_modules(
        self, canvas_course_id: str, access_token: str
    ) -> list[CanvasModule]:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            response = self._session.get(
                f"{base_url}/api/v1/courses/{canvas_course_id}/modules",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"include[]": "items", "per_page": "50"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            modules = []
            for module_data in data:
                items = []
                for item_data in module_data.get("items", []):
                    items.append(CanvasModuleItem(
                        item_id=str(item_data["id"]),
                        title=item_data.get("title", ""),
                        type=item_data.get("type", ""),
                        url=item_data.get("url"),
                        page_url=item_data.get("page_url"),
                    ))
                modules.append(CanvasModule(
                    module_id=str(module_data["id"]),
                    name=module_data.get("name", ""),
                    items=items,
                ))
            return modules
        except requests.RequestException:
            logger.exception("Failed to fetch Canvas modules")
            return []

    def get_course_files(
        self, canvas_course_id: str, access_token: str
    ) -> list[CanvasFile]:
        base_url = self._settings.CANVAS_BASE_URL.rstrip("/")
        try:
            response = self._session.get(
                f"{base_url}/api/v1/courses/{canvas_course_id}/files",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"per_page": "100"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return [
                CanvasFile(
                    file_id=str(f["id"]),
                    display_name=f.get("display_name", ""),
                    filename=f.get("filename", ""),
                    url=f.get("url"),
                    size=f.get("size", 0),
                )
                for f in data
            ]
        except requests.RequestException:
            logger.exception("Failed to fetch Canvas files")
            return []

    def get_course_modules_for_user(
        self, user: User, canvas_course_id: str
    ) -> list[CanvasModule]:
        token = self.get_or_refresh_token(user)
        if not token:
            return []
        return self.get_course_modules(canvas_course_id, token)

    def get_course_files_for_user(
        self, user: User, canvas_course_id: str
    ) -> list[CanvasFile]:
        token = self.get_or_refresh_token(user)
        if not token:
            return []
        return self.get_course_files(canvas_course_id, token)

    @staticmethod
    def _compute_token_expiry(expires_in: int) -> datetime:
        return timezone.now() + timedelta(
            seconds=expires_in or DEFAULT_TOKEN_EXPIRY_SECONDS
        )

    @transaction.atomic
    def get_or_create_user(
        self,
        info: CanvasUserInfo,
        access_token: str = "",
        refresh_token: str = "",
        expires_in: int = 0,
    ) -> tuple[User, bool]:
        token_expires_at = self._compute_token_expiry(expires_in)

        try:
            profile = CanvasProfile.objects.select_related("user").get(
                canvas_user_id=info.canvas_user_id
            )
            profile.access_token = access_token
            profile.refresh_token = refresh_token
            profile.token_expires_at = token_expires_at
            profile.save(update_fields=[
                "access_token", "refresh_token", "token_expires_at"
            ])
            return profile.user, False
        except CanvasProfile.DoesNotExist:
            pass

        if info.email:
            try:
                user = User.objects.get(email=info.email)
                CanvasProfile.objects.create(
                    user=user,
                    canvas_user_id=info.canvas_user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
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
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )

        return user, True
