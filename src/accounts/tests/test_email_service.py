"""
Tests for the EmailVerificationService.

This module tests the email verification functionality following the
service layer architecture with comprehensive coverage.
"""

from unittest.mock import patch
from django.test import TestCase, RequestFactory
from django.core import mail
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, EmailVerification
from accounts.email_service import EmailVerificationService


class EmailVerificationServiceTests(TestCase):
    """Test cases for the EmailVerificationService."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="test@uw.edu",
            email="test@uw.edu",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    def test_send_verification_email_success(self):
        """Test successful verification email sending."""
        request = self.factory.get("/")

        result = EmailVerificationService.send_verification_email(self.user, request)

        # Check result
        self.assertTrue(result.success)
        self.assertIsNotNone(result.token)
        self.assertIsNone(result.error)

        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@uw.edu"])
        self.assertIn("Verify your LLTeacher account", email.subject)
        self.assertIn("verification", email.body.lower())

        # Check verification record was created
        verification = EmailVerification.objects.get(user=self.user)
        self.assertEqual(verification.token, result.token)
        self.assertFalse(verification.is_used)
        self.assertFalse(verification.is_expired())

    def test_send_verification_email_without_request(self):
        """Test verification email sending without request object."""
        result = EmailVerificationService.send_verification_email(self.user, None)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.token)

        # Check email contains localhost domain
        email = mail.outbox[0]
        self.assertIn("localhost:8000", email.body)

    @patch("accounts.email_service.send_mail")
    def test_send_verification_email_failure(self, mock_send_mail):
        """Test verification email sending failure."""
        mock_send_mail.side_effect = Exception("SMTP Error")

        result = EmailVerificationService.send_verification_email(self.user)

        self.assertFalse(result.success)
        self.assertIsNone(result.token)
        self.assertEqual(result.error, "SMTP Error")

    def test_verify_email_token_success(self):
        """Test successful email token verification."""
        # Create verification record
        verification = EmailVerification.objects.create(
            user=self.user, token="test-token-123"
        )

        result = EmailVerificationService.verify_email_token("test-token-123")

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.user_id, self.user.id)
        self.assertIsNone(result.error)

        # Check token was marked as used
        verification.refresh_from_db()
        self.assertTrue(verification.is_used)

        # Check user was marked as verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verify_email_token_invalid(self):
        """Test verification with invalid token."""
        result = EmailVerificationService.verify_email_token("invalid-token")

        self.assertFalse(result.success)
        self.assertIsNone(result.user_id)
        self.assertEqual(result.error, "Invalid verification link.")

    def test_verify_email_token_expired(self):
        """Test verification with expired token."""
        # Create expired verification record
        _verification = EmailVerification.objects.create(
            user=self.user,
            token="expired-token",
            expires_at=timezone.now() - timedelta(days=1),
        )

        result = EmailVerificationService.verify_email_token("expired-token")

        self.assertFalse(result.success)
        self.assertIsNone(result.user_id)
        self.assertEqual(
            result.error,
            "This verification link has expired. Please request a new one.",
        )

    def test_verify_email_token_already_used(self):
        """Test verification with already used token."""
        # Create used verification record
        _verification = EmailVerification.objects.create(
            user=self.user, token="used-token", is_used=True
        )

        result = EmailVerificationService.verify_email_token("used-token")

        self.assertFalse(result.success)
        self.assertIsNone(result.user_id)
        self.assertEqual(result.error, "This verification link has already been used.")

    def test_resend_verification_email_success(self):
        """Test successful verification email resending."""
        # Create old unused verification
        old_verification = EmailVerification.objects.create(
            user=self.user, token="old-token"
        )

        result = EmailVerificationService.resend_verification_email(self.user)

        # Check result
        self.assertTrue(result.success)
        self.assertIsNotNone(result.token)

        # Check old token was invalidated
        old_verification.refresh_from_db()
        self.assertTrue(old_verification.is_used)

        # Check new verification was created
        new_verification = EmailVerification.objects.filter(
            user=self.user, is_used=False
        ).first()
        self.assertIsNotNone(new_verification)
        self.assertEqual(new_verification.token, result.token)

    def test_resend_verification_email_already_verified(self):
        """Test resending verification email for already verified user."""
        self.user.is_email_verified = True
        self.user.save()

        result = EmailVerificationService.resend_verification_email(self.user)

        self.assertFalse(result.success)
        self.assertIsNone(result.token)
        self.assertEqual(result.error, "Email is already verified.")

    def test_cleanup_expired_tokens(self):
        """Test cleanup of expired verification tokens."""
        # Create expired and valid tokens
        expired_verification = EmailVerification.objects.create(
            user=self.user,
            token="expired-token",
            expires_at=timezone.now() - timedelta(days=1),
        )

        valid_verification = EmailVerification.objects.create(
            user=self.user, token="valid-token"
        )

        # Run cleanup
        count = EmailVerificationService.cleanup_expired_tokens()

        # Check results
        self.assertEqual(count, 1)

        expired_verification.refresh_from_db()
        self.assertTrue(expired_verification.is_used)

        valid_verification.refresh_from_db()
        self.assertFalse(valid_verification.is_used)

    def test_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = set()

        for _ in range(10):
            result = EmailVerificationService.send_verification_email(self.user)
            self.assertTrue(result.success)
            self.assertNotIn(result.token, tokens)
            tokens.add(result.token)

            # Clean up for next iteration
            EmailVerification.objects.filter(token=result.token).delete()

    def test_email_template_context(self):
        """Test that email templates receive correct context."""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "testserver"

        result = EmailVerificationService.send_verification_email(self.user, request)

        self.assertTrue(result.success)

        # Check email content
        email = mail.outbox[0]
        self.assertIn(self.user.first_name, email.body)
        self.assertIn("testserver", email.body)
        self.assertIn(result.token, email.body)
        self.assertIn("/accounts/verify-email/", email.body)
