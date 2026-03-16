"""
Email verification service for the accounts app.

This module provides email verification functionality following the
service layer architecture with typed data contracts.
"""

import secrets
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
from django.utils import timezone

import logging

from llteacher.tracing import traced, record_exception

from .models import User, EmailVerification

logger = logging.getLogger(__name__)


@dataclass
class EmailVerificationResult:
    """Result of an email verification operation."""

    success: bool
    user_id: Optional[UUID] = None
    error: Optional[str] = None


@dataclass
class EmailSendResult:
    """Result of sending a verification email."""

    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


class EmailVerificationService:
    """Service for managing email verification operations."""

    @staticmethod
    @traced
    def send_verification_email(user: User, request=None) -> EmailSendResult:
        """
        Send email verification email to user.

        Args:
            user: The user to send verification email to
            request: HTTP request object for building absolute URLs

        Returns:
            EmailSendResult with success status and token or error
        """
        try:
            # Generate secure token
            token = secrets.token_urlsafe(32)

            # Create verification record
            _verification = EmailVerification.objects.create(user=user, token=token)

            # Prepare email context
            context = {
                "user": user,
                "token": token,
                "protocol": "https" if request and request.is_secure() else "http",
                "domain": get_current_site(request).domain
                if request
                else "localhost:8000",
            }

            # Render email templates
            subject = "Verify your LLTeacher account"
            html_message = render_to_string(
                "accounts/emails/verification_email.html", context
            )
            text_message = render_to_string(
                "accounts/emails/verification_email.txt", context
            )

            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

            return EmailSendResult(success=True, token=token)

        except Exception as e:
            logger.exception("Error sending verification email")
            record_exception(e)
            return EmailSendResult(success=False, error=str(e))

    @staticmethod
    @traced
    def verify_email_token(token: str) -> EmailVerificationResult:
        """
        Verify an email verification token.

        Args:
            token: The verification token to check

        Returns:
            EmailVerificationResult with success status and user ID or error
        """
        try:
            # Find the verification record
            verification = EmailVerification.objects.select_related("user").get(
                token=token
            )

            # Check if token is valid
            if not verification.is_valid():
                if verification.is_used:
                    error = "This verification link has already been used."
                else:
                    error = (
                        "This verification link has expired. Please request a new one."
                    )

                return EmailVerificationResult(success=False, error=error)

            # Mark token as used
            verification.is_used = True
            verification.save()

            # Mark user email as verified
            user = verification.user
            user.is_email_verified = True
            user.save()

            return EmailVerificationResult(success=True, user_id=user.id)

        except EmailVerification.DoesNotExist:
            return EmailVerificationResult(
                success=False, error="Invalid verification link."
            )
        except Exception as e:
            logger.exception("Error verifying email token")
            record_exception(e)
            return EmailVerificationResult(success=False, error=str(e))

    @staticmethod
    @traced
    def resend_verification_email(user: User, request=None) -> EmailSendResult:
        """
        Resend verification email to user.

        Args:
            user: The user to resend verification email to
            request: HTTP request object for building absolute URLs

        Returns:
            EmailSendResult with success status and token or error
        """
        # Check if user is already verified
        if user.is_email_verified:
            return EmailSendResult(success=False, error="Email is already verified.")

        # Invalidate any existing unused tokens
        EmailVerification.objects.filter(user=user, is_used=False).update(is_used=True)

        # Send new verification email
        return EmailVerificationService.send_verification_email(user, request)

    @staticmethod
    @traced
    def cleanup_expired_tokens():
        """
        Clean up expired verification tokens.

        This method can be called periodically to remove old tokens.
        """
        expired_count = EmailVerification.objects.filter(
            expires_at__lt=timezone.now(), is_used=False
        ).update(is_used=True)

        return expired_count
