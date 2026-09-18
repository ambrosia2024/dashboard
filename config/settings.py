# config/settings.py

import os
import sys

from dotenv import load_dotenv
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path, override=False):
    if path.exists():
        load_dotenv(path, override=override)


# Load shared defaults first, then environment-specific overrides.
# Do not let `.env` overwrite process-level environment variables provided by Docker/Compose.
_load_env_file(BASE_DIR / ".env", override=False)

# Detect if running inside Docker before loading environment-specific overlays.
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "False").lower() == "true"

if RUNNING_IN_DOCKER:
    _load_env_file(BASE_DIR / ".env.docker", override=True)
else:
    _load_env_file(BASE_DIR / ".env.local", override=True)

from decouple import config, UndefinedValueError

from celery.schedules import crontab

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# Feature flag: turn email verification on/off
EMAIL_VERIFICATION_ENABLED = os.getenv("EMAIL_VERIFICATION_ENABLED", "false").lower() == "true"
PUBLIC_SIGNUP_ENABLED = os.getenv("PUBLIC_SIGNUP_ENABLED", "false").lower() == "true"
RECAPTCHA_ENABLED = os.getenv("RECAPTCHA_ENABLED", "false").lower() == "true"
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
# Transactional email. With Postmark, one Server API token is both the SMTP
# username and password; POSTMARK_SERVER_TOKEN takes precedence over the
# generic EMAIL_HOST_USER/PASSWORD pair when set.
POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN", "").strip()
POSTMARK_MESSAGE_STREAM = os.getenv("POSTMARK_MESSAGE_STREAM", "outbound").strip()
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.postmarkapp.com" if POSTMARK_SERVER_TOKEN else "").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = POSTMARK_SERVER_TOKEN or os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = POSTMARK_SERVER_TOKEN or os.getenv("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Ambrosia Dashboard <noreply@ambrosia-project.eu>").strip()
SERVER_EMAIL = os.getenv("SERVER_EMAIL", "noreply@ambrosia-project.eu").strip()
EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "").strip()  # optional, e.g. support@ambrosia-project.eu
SCW_AI_BASE_URL = os.getenv(
    "SCW_AI_BASE_URL",
    "https://api.scaleway.ai/6ca646d5-bc15-44af-bce4-43e83b3866a5/v1",
).strip()
SCW_SECRET_KEY = os.getenv("SCW_SECRET_KEY", "").strip()
SCW_AI_MODEL = os.getenv("SCW_AI_MODEL", "qwen3.5-397b-a17b").strip()
SCW_AI_MAX_TOKENS = int(os.getenv("SCW_AI_MAX_TOKENS", "1024"))
# qwen3.5-397b-a17b reasons by default and emits its chain of thought into
# `reasoning` before any `content`, which pushes time-to-first-token past 10s.
# "none" turns reasoning off; set to "low"/"medium"/"high" to trade latency for depth.
SCW_AI_REASONING_EFFORT = os.getenv("SCW_AI_REASONING_EFFORT", "none").strip()
SCW_AI_MAX_USER_CHARS = int(os.getenv("SCW_AI_MAX_USER_CHARS", "1000"))
SCW_AI_TEMPERATURE = float(os.getenv("SCW_AI_TEMPERATURE", "0.6"))
SCW_AI_TOP_P = float(os.getenv("SCW_AI_TOP_P", "0.95"))
SCW_AI_PRESENCE_PENALTY = float(os.getenv("SCW_AI_PRESENCE_PENALTY", "0"))
SCW_AI_TIMEOUT_SECONDS = int(os.getenv("SCW_AI_TIMEOUT_SECONDS", "180"))

# Django's default config only attaches handlers to the `django` loggers, so
# `lumenix.*` INFO records (e.g. the chart_qa upstream timings) never reach the
# container log. Give the app logger its own console handler.
LUMENIX_LOG_LEVEL = os.getenv("LUMENIX_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "lumenix": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "lumenix"},
    },
    "loggers": {
        "lumenix": {"handlers": ["console"], "level": LUMENIX_LOG_LEVEL, "propagate": False},
    },
}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = not RUNNING_IN_DOCKER  # Debug True in local, False in Docker

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "dashboard.ambrosia-project.eu"]

if RUNNING_IN_DOCKER:
    ALLOWED_HOSTS.append(os.getenv("ALLOWED_HOST", "*"))  # Allow all in prod

CSRF_TRUSTED_ORIGINS = [
    "https://dashboard.ambrosia-project.eu", "http://localhost:8000", "https://dev.dashboard.ambrosia-project.eu"
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if not RUNNING_IN_DOCKER:
    # Local runserver is typically plain HTTP on 127.0.0.1:8000.
    # Secure cookies won't be set over HTTP, which breaks CSRF-protected POSTs.
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

if RUNNING_IN_DOCKER:
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_json_widget',

    # Dashboard app
    'lumenix',

    # Django REST Framework
    'rest_framework',

    # Authentication
    'django.contrib.sites',
    'allauth',
    'allauth.account',

    'django.contrib.gis',  # Required for GeoDjango/PostGIS
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'lumenix.middleware.AdminLoginProtectionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'allauth.account.middleware.AccountMiddleware',

    'lumenix.middleware.EnforceProfileCompletionMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'lumenix.context_processors.risk_context_data',
                'lumenix.context_processors.auth_flags',
                'lumenix.context_processors.user_preferences',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTHENTICATION_BACKENDS = [
    'allauth.account.auth_backends.AuthenticationBackend',  # Enables django-allauth
    'lumenix.auth_backends.EmailOrUsernameModelBackend',
]

SITE_ID = 1  # Required for django-allauth

# Allauth Settings
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_UNIQUE_EMAIL = True

# If EMAIL_VERIFICATION_ENABLED is False:
#   - no verification emails are sent
#   - users (incl. superusers) can log in without confirming email
ACCOUNT_EMAIL_VERIFICATION = "mandatory" if EMAIL_VERIFICATION_ENABLED else "none"
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""              # subjects are written in full in templates/account/email/
ACCOUNT_EMAIL_NOTIFICATIONS = True             # password changed / reset notices (design E03)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = False  # link-based recovery (designs A04–A08)
ACCOUNT_LOGIN_BY_CODE_ENABLED = False

# ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"
ACCOUNT_LOGOUT_ON_GET = False

LOGIN_URL = "/accounts/login/"      # allauth login URL
LOGIN_REDIRECT_URL = "/overview/"   # V2 workspace; the preferences gate runs first when no role is set
ACCOUNT_ADAPTER = "lumenix.account_adapter.NoSignupAccountAdapter"

ACCOUNT_FORMS = {
    "login": "lumenix.forms.SecureLoginForm",
    "signup": "lumenix.forms.NamedSignupForm",
}

# How long a “remembered” login should last (14 days)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# How allauth treats the remember checkbox:
# - None (default): use the checkbox value
# - True: always remember (checkbox ignored)
# - False: never remember (checkbox ignored)
ACCOUNT_SESSION_REMEMBER = None

# Shared cache used by login anti-bruteforce controls.
# Redis-backed so the cache is shared across containers. The admin sync guards
# use cache.add() as a lock: the web container acquires it and the Celery worker
# releases it, which only works if both see the same store. A file-based cache
# gave each container its own copy, so worker-side releases never cleared the
# web-side lock (it then sat for its full TTL, blocking every admin sync).
# cache.add() maps to Redis SETNX, which is atomic — a shared volume would not be.
# Prefer REDIS_CACHE_URL; otherwise derive the cache URL from the Celery broker
# (always set wherever Redis exists), so a missing env var cannot silently point
# the cache at localhost. With no Redis at all — plain `runserver` locally — fall
# back to the file cache so local development needs no extra service.
_REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "").strip()
_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip()
if not _REDIS_CACHE_URL and _BROKER_URL.startswith("redis://"):
    _REDIS_CACHE_URL = _BROKER_URL.rsplit("/", 1)[0] + "/2"

if _REDIS_CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_CACHE_URL,
            "TIMEOUT": 60 * 30,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": BASE_DIR / "data" / "django_cache",
            "TIMEOUT": 60 * 30,
            "OPTIONS": {"MAX_ENTRIES": 50000},
        }
    }

# Login protection thresholds
LOGIN_BURST_LIMIT_PER_MINUTE = int(os.getenv("LOGIN_BURST_LIMIT_PER_MINUTE", "20"))

# Database
# PostgreSQL Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        # 'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("POSTGRES_DB"),
        'USER': os.getenv("POSTGRES_USER"),
        'PASSWORD': os.getenv("POSTGRES_PASSWORD"),
        'HOST': os.getenv("POSTGRES_HOST"),
        'PORT': os.getenv("POSTGRES_PORT"),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Europe/Amsterdam'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

if RUNNING_IN_DOCKER:
    STATIC_ROOT = BASE_DIR / "staticfiles"  # Use collected static files in Docker
    STATICFILES_DIRS = [BASE_DIR / "static"]
else:
    STATICFILES_DIRS = [BASE_DIR / "static"]  # Use local static files in dev

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


SCIO_VOCAB_API_BASE = os.getenv("SCIO_VOCAB_API_BASE", "https://dev.api.ambrosia.scio.services/api/vocabulary")
SCIO_NUTS_API_BASE = os.getenv("SCIO_NUTS_API_BASE", "https://dev.api.ambrosia.scio.services/api/nuts")
SCIO_MODELS_API_URL = os.getenv("SCIO_MODELS_API_URL", "https://dev.api.ambrosia.scio.services/api/models")
SCIO_PATHOGEN_QUERY_URL = os.getenv(
    "SCIO_PATHOGEN_QUERY_URL",
    "https://dev.api.ambrosia.scio.services/api/pathogen-concentration/query",
)
SCIO_PATHOGEN_AVAILABLE_START_DATE = os.getenv("SCIO_PATHOGEN_AVAILABLE_START_DATE", "1971-01-01")
SCIO_PATHOGEN_AVAILABLE_END_DATE = os.getenv("SCIO_PATHOGEN_AVAILABLE_END_DATE", "2095-12-31")
SCIO_PATHOGEN_SYNC_CHUNK_DAYS = int(os.getenv("SCIO_PATHOGEN_SYNC_CHUNK_DAYS", "7"))
SCIO_PATHOGEN_SYNC_REQUEST_DELAY_SECONDS = float(os.getenv("SCIO_PATHOGEN_SYNC_REQUEST_DELAY_SECONDS", "2"))
SCIO_PATHOGEN_SYNC_CHUNK_MAX_RETRIES = int(os.getenv("SCIO_PATHOGEN_SYNC_CHUNK_MAX_RETRIES", "2"))
SCIO_PATHOGEN_SYNC_MAX_CONSECUTIVE_FAILURES = int(os.getenv("SCIO_PATHOGEN_SYNC_MAX_CONSECUTIVE_FAILURES", "5"))

# Broker/result (Redis example)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip()
CELERY_TIMEZONE = os.getenv("CELERY_TIMEZONE", "Europe/Amsterdam").strip()
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# How long the auto-resume pathogen sync holds its run-lock before it auto-expires.
PATHOGEN_AUTO_SYNC_LOCK_TTL = int(os.getenv("PATHOGEN_AUTO_SYNC_LOCK_TTL", str(6 * 60 * 60)))

# Number of pending specs synced per beat tick (overlapping ticks are skipped via lock).
PATHOGEN_AUTO_SYNC_BATCH_SIZE = int(os.getenv("PATHOGEN_AUTO_SYNC_BATCH_SIZE", "10"))

# Beat runs with no successful chunk before a spec is parked, so a permanently
# failing spec cannot retry every 5 minutes forever. Any progress resets it.
PATHOGEN_AUTO_SYNC_MAX_FAILED_RUNS = int(os.getenv("PATHOGEN_AUTO_SYNC_MAX_FAILED_RUNS", "5"))

# Set true to re-download chunks already stored locally (a refresh, not a resume).
SCIO_PATHOGEN_SYNC_REFETCH_COMPLETE_CHUNKS = os.getenv(
    "SCIO_PATHOGEN_SYNC_REFETCH_COMPLETE_CHUNKS", "false"
)

CELERY_BEAT_SCHEDULE = {
    # Self-resuming pathogen sync: drains the backlog of pending PathogenQuerySpecs,
    # then becomes a no-op (no SCiO calls) once everything has last_synced_at.
    "auto-sync-pending-pathogen": {
        "task": "lumenix.tasks.auto_sync_pending_pathogen_specs_task",
        "schedule": crontab(minute="*/5"),
        "kwargs": {"batch_size": PATHOGEN_AUTO_SYNC_BATCH_SIZE},
    },
}
