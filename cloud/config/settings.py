"""
Parkinox Cloud — reporting replica + management dashboard settings.
"""
from pathlib import Path

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('CLOUD_SECRET_KEY', default='dev-cloud-secret-change-me')
DEBUG = config('CLOUD_DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('CLOUD_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'replica',
    'ingest',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.pilot_auth',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

if config('CLOUD_DB_ENGINE', default='sqlite') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('CLOUD_DB_NAME', default='parkinox_cloud'),
            'USER': config('CLOUD_DB_USER', default='parkinox'),
            'PASSWORD': config('CLOUD_DB_PASSWORD', default=''),
            'HOST': config('CLOUD_DB_HOST', default='127.0.0.1'),
            'PORT': config('CLOUD_DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Site ingest (machine) — separate from human dashboard login
SITE_INGEST_TOKEN = config('CLOUD_SITE_INGEST_TOKEN', default='dev-site-ingest-token')
DEFAULT_SITE_ID = config('CLOUD_DEFAULT_SITE_ID', default='pilot-main')
DEFAULT_ORG_NAME = config('CLOUD_DEFAULT_ORG_NAME', default='Parkinox Pilot')
PARKING_CAPACITY = config('CLOUD_PARKING_CAPACITY', default=100, cast=int)

# Pilot human dashboard credentials (env only — never hardcode password in source)
DASHBOARD_USERNAME = config('DASHBOARD_USERNAME', default='admin')
DASHBOARD_PASSWORD = config('DASHBOARD_PASSWORD', default='changeme-pilot')

# Optional: cloud → local SoR proxy for End Season (LAN/pilot)
LOCAL_SITE_API_URL = config('LOCAL_SITE_API_URL', default='')
LOCAL_SITE_OPERATOR_PHONE = config('LOCAL_SITE_OPERATOR_PHONE', default='')
LOCAL_SITE_OPERATOR_PASSWORD = config('LOCAL_SITE_OPERATOR_PASSWORD', default='')

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

SESSION_COOKIE_AGE = 60 * 60 * 12
CSRF_TRUSTED_ORIGINS = config(
    'CLOUD_CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8010,http://127.0.0.1:8010',
    cast=Csv(),
)
