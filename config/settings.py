import os
import sys

from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env
load_dotenv()
from decouple import config, UndefinedValueError

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# Detect if running inside Docker
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "False").lower() == "true"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = not RUNNING_IN_DOCKER  # Debug True in local, False in Docker

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if RUNNING_IN_DOCKER:
    ALLOWED_HOSTS.append(os.getenv("ALLOWED_HOST", "*"))  # Allow all in prod

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Dashboard app
    'lumenix',

    'fskx',

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
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'allauth.account.middleware.AccountMiddleware',
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
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

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


FSKX_USERNAME = config('FSKX_USERNAME')
FSKX_PASSWORD = config('FSKX_PASSWORD')

FSKX_SETTINGS = {
    'API': {
        'BASE_URL': config(f'FSKX_BASE_URL', default='https://fskx-api-gateway-service.risk-ai-cloud.com'),
        'AUTH_ENDPOINT': config('FSKX_AUTH_ENDPOINT', default='/auth-service/generateToken'),
        'REFRESH_ENDPOINT': config('FSKX_AUTH_ENDPOINT', default='/auth-service/refreshToken'),
        'GET_MODEL_ENDPOINT': config('FSKX_GET_MODEL_ENDPOINT', default='/model-execution-service/models/{model_id}'),
        'RUN_SIMULATION_ENDPOINT': config('FSKX_RUN_SIMULATION_ENDPOINT', default='/model-execution-service/simulations'),
        'GET_SIMULATION_ENDPOINT': config('FSKX_GET_SIMULATION_ENDPOINT', default='/model-execution-service/simulations/{simulation_id}'),
        'GET_PARAMS_ENDPOINT': config('FSKX_GET_PARAMS_ENDPOINT', default='/model-execution-service/parameters'),
        'GET_RESULTS_ENDPOINT': config('FSKX_GET_RESULTS_ENDPOINT', default='/model-execution-service/results'),
    },
    'CREDENTIALS':{
        'USERNAME': config(f'FSKX_USERNAME'),
        'PASSWORD': config(f'FSKX_PASSWORD')
    },
    'MODELS': {
        'SIMPLE_QMRA_ID': config("FSKX_SIMPLE_QMRA_ID", default='c42738eb-d6d6-449b-a313-6051432f536f'),
        'FSKX_SIMPLE_KOSEKI_ID': config("FSKX_SIMPLE_KOSEKI_ID", default='ac398182-01ab-48f0-b25c-ca432631b018'),
    },
    'TESTING_JSON_RISK_PATH': config("FSKX_TESTING_JSON_RISK_PATH", default='fskx/testing_data/risk_index.json'),
}
