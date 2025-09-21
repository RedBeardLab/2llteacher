"""
Tests for email domain validation functionality.

This module tests the domain validation for UW email addresses,
including subdomain support and grandfathering logic.
"""

from django.test import TestCase
from accounts.forms import RegistrationForm, ProfileForm
from accounts.models import User
from accounts.utils import is_email_domain_allowed


class TestDomainValidationUtils(TestCase):
    """Test the domain validation utility function."""

    def test_is_email_domain_allowed_exact_match(self):
        """Test exact domain match."""
        self.assertTrue(is_email_domain_allowed("user@uw.edu", ["uw.edu"]))

    def test_is_email_domain_allowed_subdomain(self):
        """Test subdomain support."""
        self.assertTrue(is_email_domain_allowed("user@cs.uw.edu", ["uw.edu"]))
        self.assertTrue(is_email_domain_allowed("user@math.uw.edu", ["uw.edu"]))
        self.assertTrue(is_email_domain_allowed("user@dept.cs.uw.edu", ["uw.edu"]))

    def test_is_email_domain_allowed_case_insensitive(self):
        """Test case insensitive matching."""
        self.assertTrue(is_email_domain_allowed("user@UW.EDU", ["uw.edu"]))
        self.assertTrue(is_email_domain_allowed("user@CS.UW.EDU", ["uw.edu"]))
        self.assertTrue(is_email_domain_allowed("user@uw.edu", ["UW.EDU"]))

    def test_is_email_domain_allowed_invalid_domain(self):
        """Test rejection of invalid domains."""
        self.assertFalse(is_email_domain_allowed("user@gmail.com", ["uw.edu"]))
        self.assertFalse(is_email_domain_allowed("user@washington.edu", ["uw.edu"]))
        self.assertFalse(is_email_domain_allowed("user@uwashington.edu", ["uw.edu"]))

    def test_is_email_domain_allowed_malformed_email(self):
        """Test handling of malformed emails."""
        self.assertFalse(is_email_domain_allowed("", ["uw.edu"]))
        self.assertFalse(is_email_domain_allowed("user", ["uw.edu"]))
        self.assertFalse(is_email_domain_allowed("user@", ["uw.edu"]))
        self.assertFalse(is_email_domain_allowed("@uw.edu", ["uw.edu"]))

    def test_is_email_domain_allowed_multiple_domains(self):
        """Test support for multiple allowed domains."""
        allowed_domains = ["uw.edu", "washington.edu"]
        self.assertTrue(is_email_domain_allowed("user@uw.edu", allowed_domains))
        self.assertTrue(is_email_domain_allowed("user@washington.edu", allowed_domains))
        self.assertTrue(is_email_domain_allowed("user@cs.uw.edu", allowed_domains))
        self.assertFalse(is_email_domain_allowed("user@gmail.com", allowed_domains))


class TestRegistrationFormDomainValidation(TestCase):
    """Test domain validation in registration form."""

    def setUp(self):
        """Set up test data."""
        self.valid_form_data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "password1": "complexpassword123",
            "password2": "complexpassword123",
            "role": "student",
        }

    def test_registration_form_valid_uw_email(self):
        """Test registration with valid UW email."""
        form_data = self.valid_form_data.copy()
        form_data["email"] = "testuser@uw.edu"
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_registration_form_valid_uw_subdomain(self):
        """Test registration with valid UW subdomain."""
        subdomains = ["cs.uw.edu", "math.uw.edu", "ee.uw.edu", "dept.cs.uw.edu"]

        for subdomain in subdomains:
            with self.subTest(subdomain=subdomain):
                form_data = self.valid_form_data.copy()
                form_data["email"] = f"testuser@{subdomain}"
                form_data["username"] = f"testuser_{subdomain.replace('.', '_')}"
                form = RegistrationForm(data=form_data)
                self.assertTrue(
                    form.is_valid(), f"Form errors for {subdomain}: {form.errors}"
                )

    def test_registration_form_case_insensitive(self):
        """Test registration with case variations."""
        case_variations = ["UW.EDU", "CS.UW.EDU", "Uw.Edu", "cs.UW.edu"]

        for domain in case_variations:
            with self.subTest(domain=domain):
                form_data = self.valid_form_data.copy()
                form_data["email"] = f"testuser@{domain}"
                form_data["username"] = f"testuser_{domain.replace('.', '_').lower()}"
                form = RegistrationForm(data=form_data)
                self.assertTrue(
                    form.is_valid(), f"Form errors for {domain}: {form.errors}"
                )

    def test_registration_form_invalid_domain(self):
        """Test registration rejection with invalid domain."""
        invalid_domains = [
            "gmail.com",
            "washington.edu",
            "uwashington.edu",
            "yahoo.com",
            "hotmail.com",
            "uw.com",
            "edu.uw",
        ]

        for domain in invalid_domains:
            with self.subTest(domain=domain):
                form_data = self.valid_form_data.copy()
                form_data["email"] = f"testuser@{domain}"
                form_data["username"] = f"testuser_{domain.replace('.', '_')}"
                form = RegistrationForm(data=form_data)
                self.assertFalse(form.is_valid())
                self.assertIn(
                    "Email must be from University of Washington domain",
                    str(form.errors),
                )

    def test_registration_form_duplicate_email(self):
        """Test that duplicate email validation still works."""
        # Create a user first
        User.objects.create_user(
            username="existinguser", email="existing@uw.edu", password="password123"
        )

        # Try to register with same email
        form_data = self.valid_form_data.copy()
        form_data["email"] = "existing@uw.edu"
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("A user with that email already exists", str(form.errors))


class TestProfileFormDomainValidation(TestCase):
    """Test domain validation in profile form with grandfathering logic."""

    def setUp(self):
        """Set up test users."""
        # User with UW email
        self.uw_user = User.objects.create_user(
            username="uwuser", email="uwuser@uw.edu", password="password123"
        )

        # User with non-UW email (grandfathered)
        self.legacy_user = User.objects.create_user(
            username="legacyuser", email="legacy@gmail.com", password="password123"
        )

    def test_profile_form_uw_user_change_within_uw(self):
        """Test UW user changing to another UW email."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@cs.uw.edu",
        }
        form = ProfileForm(data=form_data, instance=self.uw_user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_profile_form_uw_user_change_to_invalid(self):
        """Test UW user trying to change to invalid domain."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@gmail.com",
        }
        form = ProfileForm(data=form_data, instance=self.uw_user)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "New email domain must be from University of Washington", str(form.errors)
        )

    def test_profile_form_legacy_user_keep_same_domain(self):
        """Test legacy user keeping same non-UW domain (grandfathered)."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@gmail.com",  # Same domain as original
        }
        form = ProfileForm(data=form_data, instance=self.legacy_user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_profile_form_legacy_user_change_to_uw(self):
        """Test legacy user changing to UW domain (allowed)."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@uw.edu",
        }
        form = ProfileForm(data=form_data, instance=self.legacy_user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_profile_form_legacy_user_change_to_different_invalid(self):
        """Test legacy user trying to change to different invalid domain."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@yahoo.com",  # Different domain from original gmail.com
        }
        form = ProfileForm(data=form_data, instance=self.legacy_user)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "New email domain must be from University of Washington", str(form.errors)
        )

    def test_profile_form_same_username_different_domain(self):
        """Test changing just the username part of email (same domain)."""
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "differentusername@uw.edu",  # Same domain as original
        }
        form = ProfileForm(data=form_data, instance=self.uw_user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_profile_form_duplicate_email_validation(self):
        """Test that duplicate email validation still works in profile form."""
        # Try to change to existing user's email
        form_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "uwuser@uw.edu",  # This is the uw_user's email
        }
        form = ProfileForm(data=form_data, instance=self.legacy_user)
        self.assertFalse(form.is_valid())
        self.assertIn("A user with that email already exists", str(form.errors))


class TestDomainValidationIntegration(TestCase):
    """Integration tests for domain validation across the system."""

    def test_settings_configuration(self):
        """Test that settings are properly configured."""
        from django.conf import settings

        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
        self.assertIn("uw.edu", allowed_domains)

    def test_no_allowed_domains_setting(self):
        """Test behavior when ALLOWED_EMAIL_DOMAINS is not set."""
        # This test ensures the system gracefully handles missing settings
        with self.settings(ALLOWED_EMAIL_DOMAINS=[]):
            form_data = {
                "username": "testuser",
                "email": "testuser@gmail.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "complexpassword123",
                "password2": "complexpassword123",
                "role": "student",
            }
            form = RegistrationForm(data=form_data)
            # Should be valid when no domains are configured
            self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")


class TestClientSideValidationPatterns(TestCase):
    """Test client-side validation pattern generation."""

    def test_single_domain_pattern_generation(self):
        """Test HTML pattern generation for single domain."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=["uw.edu"]):
            form = RegistrationForm()
            email_field = form.fields["email"]

            pattern = email_field.widget.attrs.get("pattern")
            title = email_field.widget.attrs.get("title")

            expected_pattern = r".+@(.+)*(uw\.edu)$"
            expected_title = "Please enter a valid email address from allowed domains: @uw.edu or subdomain"

            self.assertEqual(pattern, expected_pattern)
            self.assertEqual(title, expected_title)

    def test_multiple_domains_pattern_generation(self):
        """Test HTML pattern generation for multiple domains."""
        with self.settings(
            ALLOWED_EMAIL_DOMAINS=["uw.edu", "washington.edu", "example.org"]
        ):
            form = RegistrationForm()
            email_field = form.fields["email"]

            pattern = email_field.widget.attrs.get("pattern")
            title = email_field.widget.attrs.get("title")

            expected_pattern = r".+@(.+)*(uw\.edu|washington\.edu|example\.org)$"
            expected_title = "Please enter a valid email address from allowed domains: @uw.edu, @washington.edu, or @example.org (including subdomains)"

            self.assertEqual(pattern, expected_pattern)
            self.assertEqual(title, expected_title)

    def test_no_domain_restrictions_pattern(self):
        """Test HTML pattern when no domain restrictions are set."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=[]):
            form = RegistrationForm()
            email_field = form.fields["email"]

            pattern = email_field.widget.attrs.get("pattern")
            title = email_field.widget.attrs.get("title")

            # Should have no pattern when no restrictions
            self.assertIsNone(pattern)
            self.assertEqual(title, "Please enter a valid email address")

    def test_pattern_html_rendering(self):
        """Test that pattern attributes are properly rendered in HTML."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=["uw.edu"]):
            form = RegistrationForm()
            email_field = form.fields["email"]

            html_output = str(email_field.widget.render("email", None))

            # Verify the HTML contains our pattern and title attributes
            self.assertIn("pattern=", html_output)
            self.assertIn("uw\.edu", html_output)
            self.assertIn("title=", html_output)
            self.assertIn("allowed domains", html_output)

    def test_special_characters_in_domains(self):
        """Test proper escaping of special regex characters in domains."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=["test.edu", "sub.domain.edu"]):
            form = RegistrationForm()
            email_field = form.fields["email"]

            pattern = email_field.widget.attrs.get("pattern")

            # Pattern should not be None for this test
            self.assertIsNotNone(pattern)

            # Ensure pattern is a string before using string methods
            if pattern:
                # Dots should be escaped in the pattern
                self.assertIn(r"test\.edu", pattern)
                self.assertIn(r"sub\.domain\.edu", pattern)
                # Should not contain unescaped dots that would match any character
                self.assertNotIn("test.edu", pattern.replace(r"test\.edu", ""))
