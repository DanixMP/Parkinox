"""
Development settings for Parkinox project.
Extends base settings with development-specific configurations.
"""

from .base import *

# Override DEBUG for development
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# Development-specific installed apps
INSTALLED_APPS += [
    # Add development-specific apps here if needed
]

# Development database configuration - using SQLite for easier setup
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Console email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable HTTPS redirect in development
SECURE_SSL_REDIRECT = False

# Development logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True
