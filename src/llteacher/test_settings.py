"""
Test settings for LLTeacher project.
This file inherits from the main settings and overrides specific settings for testing.
"""

from typing import Any, cast

from .settings import *  # noqa: F403

# Use in-memory database for testing (faster and isolated)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable password hashing for faster tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable debug mode for tests
DEBUG = False

# Use a faster secret key for tests
SECRET_KEY = "test-secret-key-for-testing-only"

# Disable logging during tests for cleaner output
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
    },
}

# Disable static files collection during tests
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Use console email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable cache during tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Disable middleware that's not needed for tests
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# Test-specific app settings
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "llteacher",
    "accounts",
    "conversations",
    "courses",
    "homeworks",
    "llm",
]

# Disable template debugging for faster tests
templates = cast(list[dict[str, Any]], TEMPLATES)  # noqa: F405
templates[0]["OPTIONS"]["debug"] = False

# Use faster timezone for tests
USE_TZ = False
TIME_ZONE = "UTC"
