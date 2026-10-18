"""
Django settings for the PayBlood project.

Environment-driven configuration. All secrets and environment-specific values
come from the root `.env` file (gitignored); the repository only tracks the
placeholder template `.env.example`. See implementation-contract.md item 7.
"""

from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is backend/; the repository-root `.env` sits one level above.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, True),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, ["http://localhost:4200", "http://127.0.0.1:4200", "https://payblood.netlify.app"]),
)
environ.Env.read_env(BASE_DIR.parent / ".env")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# SECURITY INVARIANT: no default value on purpose. Django refuses to start
# without a real DJANGO_SECRET_KEY, so a developer cannot silently run with a
# placeholder. Generate one with:
#   python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY = env("DJANGO_SECRET_KEY")

# JWT signing key: separate, robust secret via environment; falls back to the
# Django secret only for local development. Production must set JWT_SIGNING_KEY.
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", default=SECRET_KEY)

# SECURITY WARNING: never enable DEBUG in production. The default is True only
# to make local development work out of the box.
DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    # JWT auth with refresh blacklist (access 10m, refresh 7d, rotation)
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # PayBlood domain apps (under backend/apps/)
    "apps.organizations",
    "apps.accounts",
    "apps.extraction",   # Slice 7 — AI invoice extraction
]

MIDDLEWARE = [
    # CORS middleware must run before CommonMiddleware (django-cors-headers
    # requirement) to add CORS headers on responses.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite by default (local development). PostgreSQL remains possible by setting
# DATABASE_URL=postgres://user:password@host:5432/name in `.env`; credentials
# never appear in code. psycopg is pinned so the switch needs no new install.
DATABASES = {"default": env.db_url("DATABASE_URL", default="sqlite:///db.sqlite3")}

# Local SQLite: wait for the lock instead of failing fast when the dev server
# fires concurrent requests (avoids spurious "database is locked" on login/refresh).
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 20

# ---------------------------------------------------------------------------
# Password validation (Django defaults)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# ---------------------------------------------------------------------------
# Static files (CSS, JavaScript, Images)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"

# Local storage for future invoice uploads. Values are public paths only; file
# storage and retention policy are defined in the phase that introduces uploads.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR.parent / "media"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Baseline: token auth for the API, session auth for the browsable API and
    # admin. Login/token issuance is not implemented yet (planned slice); this
    # slice only verifies the tenant-scoped endpoints.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Fail closed by default: every DRF view requires an authenticated user
    # unless a view declares otherwise.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Anonymous and authenticated throttle rates (Slice 5). The login and
    # set-password endpoints use a dedicated 30/min anonymous throttle to
    # slow brute force without a new dependency.
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "120/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": False,
}

# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
# Browser origins allowed to call the API. The Angular dev server is the
# default; tighten for production (the API is not meant to be public).
CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS")
# Credentials (HttpOnly refresh cookie) are allowed only toward the explicit
# origins above — never a wildcard with credentials.
CORS_ALLOW_CREDENTIALS = True

# Refresh-token cookie: HttpOnly transport for the SPA (JS never reads it).
# SameSite=None + Secure is required for dev cross-site (localhost:4200 ->
# localhost:8000); production must serve the backend over HTTPS.
REFRESH_COOKIE_NAME = "pb_refresh"
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=True)
REFRESH_COOKIE_SAMESITE = env("REFRESH_COOKIE_SAMESITE", default="None")

# ---------------------------------------------------------------------------
# AI extraction configuration (reserved for a later phase; not used yet)
# ---------------------------------------------------------------------------
# INVARIANT (implementation-contract.md items 1 and 3): the AI only extracts
# and structures invoice data; it never approves invoices and never makes
# financial decisions. Provider credentials are read from the environment at
# runtime and must never be committed or shipped to the frontend.
AI_PROVIDER = env("AI_PROVIDER", default="")
AI_MODEL = env("AI_MODEL", default="")
AI_API_KEY = env("AI_API_KEY", default="")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", default="")
# Mock scenario for tests: 'success' | 'partial' | 'error' | 'timeout' | 'malformed'
AI_MOCK_SCENARIO = env("AI_MOCK_SCENARIO", default="success")

# ── Extraction (Slice 7) ──────────────────────────────────────────────────────
# Max upload file size in MB (server-side enforcement; default 10 MB).
EXTRACTION_MAX_FILE_SIZE_MB   = env.int("EXTRACTION_MAX_FILE_SIZE_MB",   default=10)
# Max PDF pages to process per document.
EXTRACTION_MAX_PDF_PAGES      = env.int("EXTRACTION_MAX_PDF_PAGES",      default=10)
# Timeout (seconds) for AI provider API calls.
EXTRACTION_AI_TIMEOUT_SECONDS = env.int("EXTRACTION_AI_TIMEOUT_SECONDS", default=60)

# Default primary key field type.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
