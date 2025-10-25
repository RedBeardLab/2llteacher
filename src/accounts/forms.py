"""
Forms for the accounts app.

This module provides forms for user registration and authentication,
following the testable-first architecture.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.conf import settings
from .utils import is_email_domain_allowed

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """Form for student registration."""

    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "First name"}
        ),
    )

    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last name"}
        ),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)

        # Generate dynamic pattern and title based on allowed domains
        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
        if allowed_domains:
            # Create regex pattern for multiple domains
            # Example: for ['uw.edu', 'washington.edu'] -> (uw\.edu|washington\.edu)
            escaped_domains = [domain.replace(".", r"\.") for domain in allowed_domains]
            domains_pattern = "|".join(escaped_domains)
            pattern = f".+@(.+)*({domains_pattern})$"

            # Create user-friendly title message
            if len(allowed_domains) == 1:
                domain_text = f"@{allowed_domains[0]} or subdomain"
            else:
                domain_list = ", ".join(f"@{domain}" for domain in allowed_domains[:-1])
                domain_text = (
                    f"{domain_list}, or @{allowed_domains[-1]} (including subdomains)"
                )

            title = f"Please enter a valid email address from allowed domains: {domain_text}"
        else:
            # No domain restrictions
            pattern = None
            title = "Please enter a valid email address"

        # Update email field widget attributes
        email_attrs = {
            "class": "form-control",
            "placeholder": "Email address",
            "title": title,  # Always set title, even when no pattern
        }
        if pattern:
            email_attrs["pattern"] = pattern

        self.fields["email"] = forms.EmailField(
            required=True, widget=forms.EmailInput(attrs=email_attrs)
        )

        # Override default labels and help texts for password fields
        self.fields["password1"].widget = forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        )
        self.fields["password2"].widget = forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm password"}
        )

        # Override help_text for better display
        self.fields[
            "password1"
        ].help_text = (
            "Your password must be at least 8 characters long and not too common."
        )
        self.fields[
            "password2"
        ].help_text = "Enter the same password as before, for verification."

    def save(self, commit=True):
        """Save the user with email as username."""
        user = super().save(commit=False)
        # Use email as username
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

    def clean_email(self):
        """Validate that the email is unique and from allowed domain."""
        email = self.cleaned_data.get("email")

        # Existing uniqueness check
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")

        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
        if (
            allowed_domains
            and email
            and not is_email_domain_allowed(email, allowed_domains)
        ):
            raise ValidationError(
                "Email must be from University of Washington domain (@uw.edu or subdomain). "
                "Please use your UW email address."
            )

        return email


class LoginForm(AuthenticationForm):
    """Form for user login."""

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        )
    )

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.error_messages.update(
            {
                "invalid_login": "Please enter a correct username and password. Note that both fields may be case-sensitive.",
                "inactive": "This account is inactive.",
            }
        )


class ProfileForm(forms.ModelForm):
    """Form for editing user profile."""

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "First Name"}
        ),
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last Name"}
        ),
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ProfileForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        """Validate that the email is unique."""
        email = self.cleaned_data.get("email")

        # Existing uniqueness check
        if (
            email
            and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists()
        ):
            raise ValidationError("A user with that email already exists.")

        # For profile updates, we'll be more lenient with domain validation
        # Only enforce domain restrictions if the user is changing to a completely new domain
        # This grandfathers in existing users with non-UW emails
        if email and self.instance.email:
            old_domain = self.instance.email.split("@")[-1].lower()
            new_domain = email.split("@")[-1].lower()

            # If they're changing domains (not just the username part), enforce restrictions
            if old_domain != new_domain:
                allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
                if allowed_domains and not is_email_domain_allowed(
                    email, allowed_domains
                ):
                    raise ValidationError(
                        "New email domain must be from University of Washington (@uw.edu or subdomain). "
                        "Please use your UW email address."
                    )

        return email
