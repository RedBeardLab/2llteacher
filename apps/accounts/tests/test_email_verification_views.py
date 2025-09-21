"""
Tests for the Email Verification Views.

This module tests the email verification view functionality with comprehensive coverage.
"""

from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages

from accounts.models import EmailVerification

User = get_user_model()


class EmailVerificationViewTests(TestCase):
    """Test cases for the EmailVerificationView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test@uw.edu",
            email="test@uw.edu",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    def test_verify_email_valid_token(self):
        """Test email verification with valid token."""
        # Create verification record
        verification = EmailVerification.objects.create(
            user=self.user, token="valid-token-123"
        )

        url = reverse("accounts:verify_email", kwargs={"token": "valid-token-123"})
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verified.html")

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("successfully verified", str(messages[0]))

        # Check user was verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

        # Check token was marked as used
        verification.refresh_from_db()
        self.assertTrue(verification.is_used)

    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token."""
        url = reverse("accounts:verify_email", kwargs={"token": "invalid-token"})
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verified.html")
        self.assertIn("error", response.context)

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("invalid verification link", str(messages[0]).lower())

        # Check user was not verified
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_expired_token(self):
        """Test email verification with expired token."""
        from django.utils import timezone
        from datetime import timedelta

        # Create expired verification record
        _verification = EmailVerification.objects.create(
            user=self.user,
            token="expired-token",
            expires_at=timezone.now() - timedelta(days=1),
        )

        url = reverse("accounts:verify_email", kwargs={"token": "expired-token"})
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verified.html")
        self.assertIn("error", response.context)

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("expired", str(messages[0]))

        # Check user was not verified
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_already_used_token(self):
        """Test email verification with already used token."""
        # Create used verification record
        _verification = EmailVerification.objects.create(
            user=self.user, token="used-token", is_used=True
        )

        url = reverse("accounts:verify_email", kwargs={"token": "used-token"})
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verified.html")
        self.assertIn("error", response.context)

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("already been used", str(messages[0]))


class ResendVerificationViewTests(TestCase):
    """Test cases for the ResendVerificationView."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test@uw.edu",
            email="test@uw.edu",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        self.url = reverse("accounts:resend_verification")

    def test_resend_verification_unauthenticated(self):
        """Test resend verification requires authentication."""
        response = self.client.get(self.url)

        # Check redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_resend_verification_success(self):
        """Test successful verification email resending."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verification_sent.html")

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("resent", str(messages[0]))

        # Check verification record was created
        verification = EmailVerification.objects.filter(
            user=self.user, is_used=False
        ).first()
        self.assertIsNotNone(verification)

    def test_resend_verification_already_verified(self):
        """Test resend verification for already verified user."""
        self.user.is_email_verified = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        # Check redirect to profile
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/profile/")

        # Check info message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("already verified", str(messages[0]))

    @patch("accounts.email_service.EmailVerificationService.resend_verification_email")
    def test_resend_verification_email_failure(self, mock_resend):
        """Test resend verification when email sending fails."""
        from accounts.email_service import EmailSendResult

        mock_resend.return_value = EmailSendResult(success=False, error="SMTP Error")

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/email_verification_sent.html")

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("SMTP Error", str(messages[0]))

    def test_resend_verification_invalidates_old_tokens(self):
        """Test that resending verification invalidates old tokens."""
        # Create old verification
        old_verification = EmailVerification.objects.create(
            user=self.user, token="old-token"
        )

        self.client.force_login(self.user)
        _response = self.client.get(self.url)

        # Check old token was invalidated
        old_verification.refresh_from_db()
        self.assertTrue(old_verification.is_used)

        # Check new token was created
        new_verification = EmailVerification.objects.filter(
            user=self.user, is_used=False
        ).first()
        self.assertIsNotNone(new_verification)
        self.assertNotEqual(new_verification.token, "old-token")
