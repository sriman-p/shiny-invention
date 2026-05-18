"""
Django settings for the ReqLens project.

This is the central configuration file for the Django backend. It controls:
  - Security: secret key, debug mode, allowed hosts
  - Database: SQLite by default (Postgres available via docker-compose)
  - Installed apps: Django core, DRF, CORS headers, and the ReqLens core app
  - Middleware: CORS must be first to handle preflight OPTIONS requests
  - REST framework: JSON-only rendering (no browsable API in production)
  - CORS: allows all origins in debug mode, restricts to localhost:3000 otherwise
  - Logging: JSON-formatted logs to both console and file

Environment variables:
  - DJANGO_SECRET_KEY: cryptographic secret (MUST change in production)
  - DJANGO_DEBUG: set to "1" for debug mode (default), "0" for production

The .env file is loaded from the repository root (two directories up from this file)
using python-dotenv. See .env.example for available settings.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from the .env file at the repository root.
# This file is not committed to git; see .env.example for the template.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def _set_env_alias(target: str, *aliases: str) -> None:
    """Populate a canonical env var from legacy/alternate names.

    ReqLens primarily documents API keys in `.env.example`. This helper exists
    to keep local developer setups working when older variable names are used.
    """

    if os.environ.get(target):
        return

    for alias in aliases:
        value = os.environ.get(alias)
        if value:
            os.environ[target] = value
            return


# Back-compat: some setups use `cursor_sdk` instead of `CURSOR_API_KEY`.
_set_env_alias("CURSOR_API_KEY", "cursor_sdk", "CURSOR_SDK", "CURSOR_SDK_API_KEY")

# Base directory for the backend: /workspace/backend/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
# The default is only suitable for development.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

# Allow all hosts in development. In production, restrict to your domain.
ALLOWED_HOSTS = ["*"]

# -- Application definition --
# Django core apps provide admin, auth, sessions, etc.
# Third-party: rest_framework for the REST API, corsheaders for CORS.
# Project: core is the main ReqLens application.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "core.apps.CoreConfig",
]

# Middleware execution order matters:
# 1. CorsMiddleware must be first to handle CORS preflight requests before
#    Django's CSRF protection rejects them.
# 2. SecurityMiddleware adds security headers (HSTS, etc.)
# 3. SessionMiddleware + AuthenticationMiddleware handle session-based auth
# 4. CsrfViewMiddleware protects against cross-site request forgery
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Points to the root URL configuration module
ROOT_URLCONF = "reqlens.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "reqlens.wsgi.application"

# -- Database --
# SQLite is used by default for simplicity. For production or concurrent access,
# switch to PostgreSQL using the docker-compose.yml Postgres service.
# The database file is stored in backend/data/reqlens.db.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "reqlens.db",
    }
}

# No password validators in development for convenience.
AUTH_PASSWORD_VALIDATORS = []

# -- Internationalization --
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Use BigAutoField for auto-generated primary keys on models that don't
# explicitly set a primary key. (ReqLens models use UUIDs instead.)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -- CORS configuration --
# In production, restrict to specific frontend origins.
# In debug mode, allow all origins for convenience during development.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
CORS_ALLOW_ALL_ORIGINS = DEBUG

# -- Django REST Framework configuration --
# JSON-only rendering: the browsable API is disabled to keep responses clean
# and to avoid accidentally exposing an HTML interface in production.
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# -- Logging configuration --
# Uses JSON format for structured log aggregation. Logs go to both the console
# (INFO level) and a file at backend/data/reqlens.log (DEBUG level).
# The "pipeline" logger is set to DEBUG for detailed tracing of pipeline execution.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": DATA_DIR / "reqlens.log",
            "formatter": "json",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "pipeline": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
