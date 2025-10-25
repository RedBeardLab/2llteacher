"""
Production settings for llteacher project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-ins3cure-change-th1s-in-production001"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Domain configuration
DOMAIN = os.environ.get("DOMAIN", "llteacher.coolify.redbeardlab.com")
ALLOWED_HOSTS = [DOMAIN, f"www.{DOMAIN}", "localhost", "127.0.0.1"]

# If DOMAIN is set to '*', allow all hosts (for development/testing)
if DOMAIN == "*":
    ALLOWED_HOSTS = ["*"]

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
    "homeworks",
    "llm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
            BASE_DIR / "apps/homeworks/templates",
            BASE_DIR / "apps/accounts/templates",
            BASE_DIR / "apps/conversations/templates",
            BASE_DIR / "apps/llm/templates",
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
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/llteacher.sqlite")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
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
STATIC_URL = "/static/"
STATIC_ROOT = "/app/staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = [
    f"https://{DOMAIN}",
    f"https://www.{DOMAIN}",
]

if DOMAIN == "*":
    CSRF_TRUSTED_ORIGINS = []

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Email domain restrictions for new registrations
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]

# Email configuration
# Environment-based email configuration for production deployment
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)

# SMTP Configuration (for production)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Email addresses and formatting
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"LLTeacher <noreply@{DOMAIN}>")
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

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {funcName} {lineno} {message}",
            "style": "{",
        },
        "request": {
            "format": "{asctime} {levelname} {name} - {message}",
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
        "request_handler": {
            "class": "logging.StreamHandler",
            "formatter": "request",
            "level": "INFO",
        },
        "timing_handler": {
            "class": "logging.StreamHandler",
            "formatter": "timing",
            "level": "INFO",
        },
    },
    "loggers": {
        # Django request logging - captures all HTTP requests
        "django.request": {
            "handlers": ["request_handler"],
            "level": "INFO",
            "propagate": False,
        },
        # Django server logging - development server requests
        "django.server": {
            "handlers": ["request_handler"],
            "level": "INFO",
            "propagate": False,
        },
        # Django database logging - SQL queries (set to WARNING to avoid spam)
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_DB_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        # Django security logging
        "django.security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # General Django framework logging
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        # Application-specific loggers
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "conversations": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "homeworks": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "llm": {
            "handlers": ["console", "timing_handler"],
            "level": "INFO",
            "propagate": False,
        },
        "services": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("ROOT_LOG_LEVEL", "INFO"),
    },
}
