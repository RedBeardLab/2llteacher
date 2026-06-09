from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

import requests

from accounts.models import User, CanvasProfile
from accounts.canvas_service import (
    CanvasOAuth2Service,
    CanvasTokenResult,
    CanvasUserInfo,
)
from accounts.views import CanvasCallbackView


class CanvasServiceGetOrCreateUserTests(TestCase):
    """Tests for CanvasOAuth2Service.get_or_create_user (real DB logic)."""

    def setUp(self):
        self.service = CanvasOAuth2Service(
            session=Mock(spec=requests.Session),
        )
        self.access_token = "test_access_token"
        self.refresh_token = "test_refresh_token"
        self.expires_in = 3600

    def _assert_tokens_persisted(self, user, expected_access, expected_refresh):
        profile = CanvasProfile.objects.get(user=user)
        self.assertEqual(profile.access_token, expected_access)
        self.assertEqual(profile.refresh_token, expected_refresh)
        self.assertIsNotNone(profile.token_expires_at)
        self.assertTrue(
            profile.token_expires_at > timezone.now()
        )

    def test_creates_new_user_with_student_profile(self):
        info = CanvasUserInfo(
            canvas_user_id="100", name="Jane Student", email="jane@uw.edu"
        )
        user, created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertTrue(created)
        self.assertEqual(user.email, "jane@uw.edu")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Student")
        self.assertTrue(user.is_email_verified)
        self.assertTrue(hasattr(user, "student_profile"))
        self._assert_tokens_persisted(user, self.access_token, self.refresh_token)

    def test_returns_existing_user_by_canvas_user_id(self):
        user = User.objects.create_user(
            username="existing@uw.edu", email="existing@uw.edu"
        )
        CanvasProfile.objects.create(user=user, canvas_user_id="200")

        info = CanvasUserInfo(
            canvas_user_id="200", name="Existing User", email="existing@uw.edu"
        )
        result, created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertFalse(created)
        self.assertEqual(result.id, user.id)
        self._assert_tokens_persisted(user, self.access_token, self.refresh_token)

    def test_links_existing_user_by_email(self):
        user = User.objects.create_user(
            username="link@uw.edu", email="link@uw.edu"
        )

        info = CanvasUserInfo(
            canvas_user_id="300", name="Link User", email="link@uw.edu"
        )
        result, created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertFalse(created)
        self.assertEqual(result.id, user.id)
        self.assertTrue(
            CanvasProfile.objects.filter(
                canvas_user_id="300", user=user
            ).exists()
        )
        self._assert_tokens_persisted(user, self.access_token, self.refresh_token)

    def test_handles_missing_email_with_login_id(self):
        info = CanvasUserInfo(
            canvas_user_id="400",
            name="No Email",
            email="",
            login_id="noemail",
        )
        user, created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertTrue(created)
        self.assertEqual(user.email, "noemail@uw.edu")
        self.assertEqual(user.username, "noemail@uw.edu")
        self._assert_tokens_persisted(user, self.access_token, self.refresh_token)

    def test_handles_missing_email_and_login_id(self):
        info = CanvasUserInfo(
            canvas_user_id="500",
            name="No Email No Login",
            email="",
            login_id="",
        )
        user, created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertTrue(created)
        self.assertEqual(user.username, "canvas_500")
        self.assertEqual(user.email, "")
        self._assert_tokens_persisted(user, self.access_token, self.refresh_token)

    def test_new_user_has_unusable_password(self):
        info = CanvasUserInfo(
            canvas_user_id="600", name="No Password", email="nopw@uw.edu"
        )
        user, _created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertFalse(user.has_usable_password())

    def test_split_name_correctly(self):
        info = CanvasUserInfo(
            canvas_user_id="700",
            name="John Michael Smith",
            email="john@uw.edu",
        )
        user, _created = self.service.get_or_create_user(
            info,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
        )
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Michael Smith")


class CanvasServiceRefreshTokenTests(TestCase):
    """Tests for CanvasOAuth2Service.refresh_access_token."""

    def setUp(self):
        self.mock_session = MagicMock(spec=requests.Session)
        self.service = CanvasOAuth2Service(session=self.mock_session)

    def test_refresh_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }
        self.mock_session.post.return_value = mock_resp

        result = self.service.refresh_access_token("old_refresh")
        self.assertTrue(result.success)
        self.assertEqual(result.access_token, "new_access")
        self.assertEqual(result.expires_in, 3600)

    def test_refresh_http_error(self):
        self.mock_session.post.side_effect = requests.RequestException("network error")

        result = self.service.refresh_access_token("bad_refresh")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class CanvasServiceGetOrRefreshTokenTests(TestCase):
    """Tests for CanvasOAuth2Service.get_or_refresh_token."""

    def setUp(self):
        self.mock_session = MagicMock(spec=requests.Session)
        self.service = CanvasOAuth2Service(session=self.mock_session)
        self.user = User.objects.create_user(
            username="test@uw.edu", email="test@uw.edu"
        )

    def test_returns_none_when_no_canvas_profile(self):
        result = self.service.get_or_refresh_token(self.user)
        self.assertIsNone(result)

    def test_returns_valid_token_when_not_expired(self):
        CanvasProfile.objects.create(
            user=self.user,
            canvas_user_id="123",
            access_token="valid_token",
            refresh_token="refresh",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        result = self.service.get_or_refresh_token(self.user)
        self.assertEqual(result, "valid_token")
        self.mock_session.post.assert_not_called()

    def test_refreshes_when_token_expired(self):
        CanvasProfile.objects.create(
            user=self.user,
            canvas_user_id="123",
            access_token="expired_token",
            refresh_token="valid_refresh",
            token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "fresh_token",
            "expires_in": 3600,
        }
        self.mock_session.post.return_value = mock_resp

        result = self.service.get_or_refresh_token(self.user)
        self.assertEqual(result, "fresh_token")

        profile = CanvasProfile.objects.get(user=self.user)
        self.assertEqual(profile.access_token, "fresh_token")
        self.assertTrue(
            profile.token_expires_at > timezone.now()
        )

    def test_returns_none_when_refresh_fails(self):
        CanvasProfile.objects.create(
            user=self.user,
            canvas_user_id="123",
            access_token="expired_token",
            refresh_token="bad_refresh",
            token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.mock_session.post.side_effect = requests.RequestException("timeout")

        result = self.service.get_or_refresh_token(self.user)
        self.assertIsNone(result)

    def test_returns_none_when_no_refresh_token(self):
        CanvasProfile.objects.create(
            user=self.user,
            canvas_user_id="123",
            access_token="expired_token",
            token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        result = self.service.get_or_refresh_token(self.user)
        self.assertIsNone(result)


class CanvasServiceExchangeCodeTests(TestCase):
    """Tests for CanvasOAuth2Service.exchange_code."""

    def setUp(self):
        self.mock_session = MagicMock(spec=requests.Session)
        self.service = CanvasOAuth2Service(session=self.mock_session)

    def test_successful_token_exchange(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 3600,
        }
        self.mock_session.post.return_value = mock_resp

        result = self.service.exchange_code("code123", "http://example.com/cb")
        self.assertTrue(result.success)
        self.assertEqual(result.access_token, "access123")
        self.assertEqual(result.refresh_token, "refresh123")
        self.assertEqual(result.expires_in, 3600)

    def test_token_exchange_defaults_expires_in(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
        }
        self.mock_session.post.return_value = mock_resp

        result = self.service.exchange_code("code123", "http://example.com/cb")
        self.assertEqual(result.expires_in, 3600)

    def test_token_exchange_http_error(self):
        self.mock_session.post.side_effect = requests.RequestException("timeout")

        result = self.service.exchange_code("badcode", "http://example.com/cb")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class CanvasServiceGetUserInfoTests(TestCase):
    """Tests for CanvasOAuth2Service.get_user_info."""

    def setUp(self):
        self.mock_session = MagicMock(spec=requests.Session)
        self.service = CanvasOAuth2Service(session=self.mock_session)

    def test_successful_user_info_fetch(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": 42,
            "name": "Test User",
            "email": "test@uw.edu",
            "login_id": "testuser",
        }
        self.mock_session.get.return_value = mock_resp

        info = self.service.get_user_info("access123")
        self.assertEqual(info.canvas_user_id, "42")
        self.assertEqual(info.name, "Test User")
        self.assertEqual(info.email, "test@uw.edu")
        self.assertEqual(info.login_id, "testuser")

    def test_user_info_http_error_raises(self):
        self.mock_session.get.side_effect = requests.RequestException("network error")

        with self.assertRaises(requests.RequestException):
            self.service.get_user_info("bad_token")


class CanvasServiceVerifyStateTests(TestCase):
    """Tests for CanvasOAuth2Service.verify_state."""

    def setUp(self):
        self.service = CanvasOAuth2Service(session=Mock(spec=requests.Session))

    def test_verify_valid_state(self):
        request = Mock()
        request.session = {"canvas_oauth_state": "expected_state"}

        result = self.service.verify_state(request, "expected_state")
        self.assertTrue(result)

    def test_verify_invalid_state(self):
        request = Mock()
        request.session = {"canvas_oauth_state": "expected_state"}

        result = self.service.verify_state(request, "wrong_state")
        self.assertFalse(result)

    def test_verify_missing_state_in_session(self):
        request = Mock()
        request.session = {}

        result = self.service.verify_state(request, "some_state")
        self.assertFalse(result)

    def test_verify_pops_state_from_session(self):
        request = Mock()
        request.session = {"canvas_oauth_state": "expected_state"}

        self.service.verify_state(request, "expected_state")
        self.assertNotIn("canvas_oauth_state", request.session)


class CanvasLoginViewTests(TestCase):
    """Tests for CanvasLoginView."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("accounts:canvas_login")

    @override_settings(
        CANVAS_CLIENT_ID="test_client_id",
        CANVAS_BASE_URL="https://canvas.uw.edu",
        CANVAS_OAUTH_SCOPES="url:GET|/api/v1/users/self",
    )
    def test_redirects_to_canvas_authorization_url(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("canvas.uw.edu/login/oauth2/auth", response.url)
        self.assertIn("client_id=", response.url)
        self.assertIn("response_type=code", response.url)
        self.assertIn("state=", response.url)
        self.assertIn("redirect_uri=", response.url)
        self.assertIn(
            "url:GET%7C/api/v1/users/self", response.url
        )

    def test_redirects_home_when_already_authenticated(self):
        user = User.objects.create_user(username="test@uw.edu", password="pw123")
        self.client.force_login(user)

        response = self.client.get(self.url)
        self.assertRedirects(response, "/")


class CanvasCallbackViewTests(TestCase):
    """Tests for CanvasCallbackView."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("accounts:canvas_callback")
        self.mock_service = Mock(spec=CanvasOAuth2Service)
        self.patcher = patch.object(
            CanvasCallbackView, "service_factory", return_value=self.mock_service
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _create_authenticatable_user(self, **kwargs):
        user = User.objects.create_user(**kwargs)
        user.backend = "django.contrib.auth.backends.ModelBackend"
        return user

    def test_new_user(self):
        self.mock_service.verify_state.return_value = True
        self.mock_service.exchange_code.return_value = CanvasTokenResult(
            success=True, access_token="tok123", expires_in=3600
        )
        self.mock_service.get_user_info.return_value = CanvasUserInfo(
            canvas_user_id="42",
            name="Jane New",
            email="jane@uw.edu",
            login_id="jane",
        )
        user = self._create_authenticatable_user(
            username="jane@uw.edu", email="jane@uw.edu"
        )
        self.mock_service.get_or_create_user.return_value = (user, True)

        response = self.client.get(self.url, {"code": "abc", "state": "xyz"})

        self.assertRedirects(response, "/")
        self.mock_service.verify_state.assert_called_once()
        self.mock_service.exchange_code.assert_called_once()
        self.mock_service.get_user_info.assert_called_once_with("tok123")
        self.mock_service.get_or_create_user.assert_called_once_with(
            self.mock_service.get_user_info.return_value,
            access_token="tok123",
            refresh_token="",
            expires_in=3600,
        )

    def test_returning_user(self):
        self.mock_service.verify_state.return_value = True
        self.mock_service.exchange_code.return_value = CanvasTokenResult(
            success=True, access_token="tok456", expires_in=3600
        )
        self.mock_service.get_user_info.return_value = CanvasUserInfo(
            canvas_user_id="99",
            name="Returning User",
            email="return@uw.edu",
        )
        user = self._create_authenticatable_user(
            username="return@uw.edu", email="return@uw.edu"
        )
        self.mock_service.get_or_create_user.return_value = (user, False)

        response = self.client.get(self.url, {"code": "cde", "state": "xyz"})

        self.assertRedirects(response, "/")

    def test_invalid_state(self):
        self.mock_service.verify_state.return_value = False

        response = self.client.get(self.url, {"code": "abc", "state": "bad"})

        self.assertRedirects(response, reverse("accounts:login"))
        self.mock_service.exchange_code.assert_not_called()

    def test_token_exchange_failure(self):
        self.mock_service.verify_state.return_value = True
        self.mock_service.exchange_code.return_value = CanvasTokenResult(
            success=False, error="bad code"
        )

        response = self.client.get(self.url, {"code": "bad", "state": "xyz"})

        self.assertRedirects(response, reverse("accounts:login"))
        self.mock_service.get_user_info.assert_not_called()

    def test_canvas_api_error(self):
        self.mock_service.verify_state.return_value = True
        self.mock_service.exchange_code.return_value = CanvasTokenResult(
            success=True, access_token="tok"
        )
        self.mock_service.get_user_info.side_effect = Exception("API down")

        response = self.client.get(self.url, {"code": "abc", "state": "xyz"})

        self.assertRedirects(response, reverse("accounts:login"))

    def test_already_authenticated(self):
        user = User.objects.create_user(username="loggedin@uw.edu", password="pw123")
        self.client.force_login(user)

        response = self.client.get(self.url, {"code": "abc", "state": "xyz"})

        self.assertRedirects(response, "/")
        self.mock_service.verify_state.assert_not_called()
