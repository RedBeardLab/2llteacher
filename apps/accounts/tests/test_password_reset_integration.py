"""
Tests for Password Reset Integration.

This module tests the complete password reset workflow including
verification that passwords are actually changed.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()


class PasswordResetIntegrationTests(TestCase):
    """Test cases for the complete password reset workflow."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test@uw.edu",
            email="test@uw.edu",
            password="old-password-123",
            first_name="Test",
            last_name="User",
        )
        self.original_password = "old-password-123"
        self.new_password = "new-password-456"

    def test_password_reset_form_renders(self):
        """Test that password reset form renders correctly."""
        url = reverse("accounts:password_reset")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_form.html")
        self.assertContains(response, "Reset Your Password")
        self.assertContains(response, "email")

    def test_password_reset_request_valid_email(self):
        """Test password reset request with valid email."""
        url = reverse("accounts:password_reset")
        data = {"email": "test@uw.edu"}

        response = self.client.post(url, data)

        # Check redirect to done page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/password-reset/done/", response.url)

        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@uw.edu"])
        self.assertIn("Password reset", email.subject)
        self.assertIn("reset your password", email.body.lower())

    def test_password_reset_request_invalid_email(self):
        """Test password reset request with invalid email."""
        url = reverse("accounts:password_reset")
        data = {"email": "nonexistent@uw.edu"}

        response = self.client.post(url, data)

        # Still redirects to done page (security - don't reveal if email exists)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/password-reset/done/", response.url)

        # No email should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_done_page(self):
        """Test password reset done page renders correctly."""
        url = reverse("accounts:password_reset_done")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_done.html")
        self.assertContains(response, "Check Your Email")
        self.assertContains(response, "emailed you instructions")

    def test_password_reset_confirm_valid_token(self):
        """Test password reset confirmation with valid token."""
        # Generate valid token
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )

        response = self.client.get(url)

        # Django redirects to a session-based URL for valid tokens
        self.assertEqual(response.status_code, 302)

        # Follow the redirect to get the actual form
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")
        self.assertContains(response, "Set New Password")
        self.assertContains(response, "new_password1")
        self.assertContains(response, "new_password2")

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirmation with invalid token."""
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = "invalid-token-123"

        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": uidb64, "token": invalid_token},
        )

        response = self.client.get(url)

        # Check invalid link message
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")
        self.assertContains(response, "Invalid Reset Link")
        self.assertContains(
            response, "invalid, possibly because it has already been used"
        )

    def test_complete_password_reset_workflow(self):
        """Test the complete password reset workflow and verify password change."""
        # Step 1: Request password reset
        reset_url = reverse("accounts:password_reset")
        response = self.client.post(reset_url, {"email": "test@uw.edu"})
        self.assertEqual(response.status_code, 302)

        # Step 2: Extract reset link from email
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body

        # Find the reset URL in the email
        import re

        url_pattern = r"http://[^/]+(/accounts/password-reset/[^/]+/[^/\s]+/)"
        match = re.search(url_pattern, email_body)
        assert match
        self.assertIsNotNone(match, "Reset URL not found in email")

        reset_confirm_path = match.group(1)

        # Step 3: Access the reset confirmation page (Django redirects for valid tokens)
        response = self.client.get(reset_confirm_path)
        if response.status_code == 302:
            # Follow redirect for valid token
            response = self.client.get(response["Location"])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set New Password")

        # Step 4: Submit new password to the current URL
        current_url = response.wsgi_request.path
        response = self.client.post(
            current_url,
            {"new_password1": self.new_password, "new_password2": self.new_password},
        )

        # Should redirect to complete page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/password-reset/complete/", response["Location"])

        # Step 5: Verify password was actually changed
        self.user.refresh_from_db()

        # Old password should no longer work
        old_auth = authenticate(username="test@uw.edu", password=self.original_password)
        self.assertIsNone(old_auth, "Old password should no longer work")

        # New password should work
        new_auth = authenticate(username="test@uw.edu", password=self.new_password)
        assert new_auth
        self.assertIsNotNone(new_auth, "New password should work")
        self.assertEqual(new_auth.pk, self.user.pk)

    def test_password_reset_complete_page(self):
        """Test password reset complete page renders correctly."""
        url = reverse("accounts:password_reset_complete")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_complete.html")
        self.assertContains(response, "Password Reset Complete")
        self.assertContains(response, "Password Successfully Changed")
        self.assertContains(response, "Log In")

    def test_password_reset_confirm_password_mismatch(self):
        """Test password reset with mismatched passwords."""
        # Generate valid token
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )

        # First access the URL to get redirected to session-based URL
        response = self.client.get(url)
        if response.status_code == 302:
            # Follow redirect for valid token
            form_url = response["Location"]
            response = self.client.get(form_url)
        else:
            form_url = url

        # Submit mismatched passwords to the form URL
        response = self.client.post(
            form_url, {"new_password1": "password123", "new_password2": "different456"}
        )

        # Should stay on same page with error
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")
        self.assertContains(response, "error")

        # Password should not have changed
        old_auth = authenticate(username="test@uw.edu", password=self.original_password)
        self.assertIsNotNone(old_auth, "Original password should still work")

    def test_password_reset_confirm_weak_password(self):
        """Test password reset with weak password."""
        # Generate valid token
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )

        # First access the URL to get redirected to session-based URL
        response = self.client.get(url)
        if response.status_code == 302:
            # Follow redirect for valid token
            form_url = response["Location"]
            response = self.client.get(form_url)
        else:
            form_url = url

        # Submit weak password to the form URL
        response = self.client.post(
            form_url, {"new_password1": "123", "new_password2": "123"}
        )

        # Should stay on same page with error
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/password_reset_confirm.html")

        # Password should not have changed
        old_auth = authenticate(username="test@uw.edu", password=self.original_password)
        self.assertIsNotNone(old_auth, "Original password should still work")

    def test_password_reset_token_expiration(self):
        """Test that password reset tokens expire properly."""
        # Generate token
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # Simulate token expiration by changing user's password
        # (this invalidates the token)
        self.user.set_password("temporary-password")
        self.user.save()

        url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )

        response = self.client.get(url)

        # Should show invalid link message
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid Reset Link")

    def test_password_reset_email_template_content(self):
        """Test that password reset email contains required content."""
        url = reverse("accounts:password_reset")
        _response = self.client.post(url, {"email": "test@uw.edu"})

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        # Check email content
        self.assertIn("Test", email.body)  # User's first name
        self.assertIn("password reset", email.body.lower())
        self.assertIn("LLTeacher", email.body)
        self.assertIn("24 hours", email.body)

        # Check both HTML and text versions exist
        self.assertIsNotNone(email.body)  # Text version
        self.assertTrue(hasattr(email, "alternatives"))  # HTML version

    def test_login_after_password_reset(self):
        """Test that user can log in after successful password reset."""
        # Complete password reset workflow
        self.test_complete_password_reset_workflow()

        # Now try to log in with new password
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url, {"username": "test@uw.edu", "password": self.new_password}
        )

        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)

        # Check user is authenticated
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.id, self.user.id)
