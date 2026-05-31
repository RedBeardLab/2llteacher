"""
Django settings for llteacher project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-your-secret-key-here"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS: list[str] = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "llteacher",  # Main project app for management commands
    "accounts",
    "conversations",
    "courses",
    "homeworks",
    "llm",
    "rag",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "llteacher.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            BASE_DIR / "src/homeworks/templates",
            BASE_DIR / "src/accounts/templates",
            BASE_DIR / "src/conversations/templates",
            BASE_DIR / "src/courses/templates",
            BASE_DIR / "src/llm/templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "llteacher.context_processors.analytics",
            ],
        },
    },
]

WSGI_APPLICATION = "llteacher.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Los_Angeles"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Email domain restrictions for new registrations
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]

# Email configuration
# Environment-based email configuration for production deployment
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# SMTP Configuration (for production)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Email addresses and formatting
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "LLTeacher <noreply@llteacher.edu>"
)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[LLTeacher] ")

# Email timeout settings
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "60"))  # seconds

# Password reset settings
PASSWORD_RESET_TIMEOUT = int(
    os.getenv("PASSWORD_RESET_TIMEOUT", "86400")
)  # 24 hours in seconds

# Email verification settings
EMAIL_VERIFICATION_TIMEOUT = int(
    os.getenv("EMAIL_VERIFICATION_TIMEOUT", "604800")
)  # 7 days in seconds

# Analytics Configuration
MICROSOFT_CLARITY_PROJECT_ID = os.getenv("MICROSOFT_CLARITY_PROJECT_ID", "tfyemkleyr")
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "True").lower() == "true"

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {funcName} {lineno} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
        "timing": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(funcName)s %(lineno)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "INFO",
        },
        "timing_handler": {
            "class": "logging.StreamHandler",
            "formatter": "timing",
            "level": "INFO",
        },
    },
    "loggers": {
        "llm": {
            "handlers": ["console", "timing_handler"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# LLM API Timeout Configuration
LLM_API_TIMEOUT = int(os.getenv("LLM_API_TIMEOUT", "30"))  # seconds
LLM_API_CONNECTION_TIMEOUT = int(
    os.getenv("LLM_API_CONNECTION_TIMEOUT", "10")
)  # seconds

# SQLite vector search extension. The sqliteai-vector package provides the
# platform-specific binary; LLTeacher loads it for every SQLite connection.
SQLITE_VECTOR_ENABLED = os.getenv("SQLITE_VECTOR_ENABLED", "True").lower() == "true"
SQLITE_VECTOR_REQUIRED = os.getenv("SQLITE_VECTOR_REQUIRED", "True").lower() == "true"

# Huey — lightweight task queue backed by SQLite
HUEY: dict = {
    "name": "llteacher",
    "filename": str(BASE_DIR / "huey.sqlite3"),
    "immediate": False,
    "consumer": {
        "workers": 2,
        "loglevel": "INFO",
    },
}

# Embedding API (OpenAI-compatible via OpenRouter)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
PAGE_GROUP_SIZE = int(os.getenv("PAGE_GROUP_SIZE", "3"))
PAGE_GROUP_STRIDE = int(os.getenv("PAGE_GROUP_STRIDE", "2"))
