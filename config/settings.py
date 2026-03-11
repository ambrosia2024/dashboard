# config/settings.py

import os
import sys

from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env
load_dotenv()
from decouple import config, UndefinedValueError

from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# Detect if running inside Docker
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "False").lower() == "true"

# Feature flag: turn email verification on/off
EMAIL_VERIFICATION_ENABLED = os.getenv("EMAIL_VERIFICATION_ENABLED", "false").lower() == "true"
PUBLIC_SIGNUP_ENABLED = os.getenv("PUBLIC_SIGNUP_ENABLED", "false").lower() == "true"
RECAPTCHA_ENABLED = os.getenv("RECAPTCHA_ENABLED", "false").lower() == "true"
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
LLM_URL = os.getenv("LLM_URL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-30b-a3b-awq").strip()
LLM_CHAT_ENDPOINT = os.getenv("LLM_CHAT_ENDPOINT", "/v1/chat/completions").strip()
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_MAX_USER_CHARS = int(os.getenv("LLM_MAX_USER_CHARS", "1000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTHENTICATION_BACKENDS = [
    'allauth.account.auth_backends.AuthenticationBackend',  # Enables django-allauth
    'django.contrib.auth.backends.ModelBackend',
]

SITE_ID = 1  # Required for django-allauth

# Allauth Settings
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}

# If EMAIL_VERIFICATION_ENABLED is False:
#   - no verification emails are sent
#   - users (incl. superusers) can log in without confirming email
ACCOUNT_EMAIL_VERIFICATION = "mandatory" if EMAIL_VERIFICATION_ENABLED else "none"
ACCOUNT_PREVENT_ENUMERATION = True

# ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"
ACCOUNT_LOGOUT_ON_GET = False

LOGIN_URL = "/accounts/login/"      # allauth login URL
LOGIN_REDIRECT_URL = "/"            # where to send user after login
ACCOUNT_ADAPTER = "lumenix.account_adapter.NoSignupAccountAdapter"

ACCOUNT_FORMS = {
    "login": "lumenix.forms.SecureLoginForm",
}

# How long a “remembered” login should last (14 days)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# How allauth treats the remember checkbox:
# - None (default): use the checkbox value
# - True: always remember (checkbox ignored)
# - False: never remember (checkbox ignored)
ACCOUNT_SESSION_REMEMBER = None

# Shared cache used by login anti-bruteforce controls.
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

# Broker/result (Redis example)
# CELERY_BROKER_URL = "redis://localhost:6379/0"
# CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
# CELERY_TIMEZONE = "Europe/Amsterdam"
# CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
#
# # Run every 5 minutes
# CELERY_BEAT_SCHEDULE = {
#     "sync-plants-hourly": {
#         "task": "lumenix.tasks.sync_vocabulary_task",
#         "schedule": crontab(minute="5", hour="*"),
#         "args": ("plants",),
#     },
#     "sync-pathogens-hourly": {
#         "task": "lumenix.tasks.sync_vocabulary_task",
#         "schedule": crontab(minute="10", hour="*"),
#         "args": ("pathogens",),
#     },
# }
