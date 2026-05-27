
from pathlib import Path
import os
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------
# DJANGO_ENV selects which env file to load (development/staging/production)
DJANGO_ENV = os.getenv('DJANGO_ENV', 'development').lower()
ENV_DIR = BASE_DIR / 'env'
DEFAULT_ENV_FILE = BASE_DIR / '.env'
ROOT_ENV_FILE = BASE_DIR / f'.env.{DJANGO_ENV}'
ENV_FILE = ENV_DIR / f'.env.{DJANGO_ENV}'

env = environ.Env(
    DEBUG=(bool, False),
)

# Load the appropriate environment file if it exists; fall back to .env
# Priority: project root env-specific file -> env/ folder -> default .env
if ROOT_ENV_FILE.exists():
    environ.Env.read_env(str(ROOT_ENV_FILE))
elif ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))
elif DEFAULT_ENV_FILE.exists():
    environ.Env.read_env(str(DEFAULT_ENV_FILE))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-()1ghb-4o_umwjwnvyd8gtne9_zshqsbt=n17-^lfm(_-a6v46')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=(DJANGO_ENV == 'development'))

ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '0.0.0.0', '192.168.174.21'],
)


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'storages',
    'accounts',
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

ROOT_URLCONF = 'CoreAPI.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'CoreAPI.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DB_ENGINE = env('DB_ENGINE', default='sqlite').lower()

if DB_ENGINE in ('postgres', 'postgresql', 'psql'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', default='coreapi'),
            'USER': env('DB_USER', default='postgres'),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='127.0.0.1'),
            'PORT': env('DB_PORT', default='5432'),
            'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=60),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': env('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
# STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (User uploads - Avatars, etc.)
# Use S3 if AWS credentials are provided, otherwise use local storage
USE_S3 = env.bool('USE_S3', default=False)

if USE_S3:
    # S3 Storage Configuration
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='')
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN', default='')  # For CloudFront CDN
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',  # 1 day cache
    }
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False  # Don't add query string auth to URLs
    
    # S3 Storage Backend
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
    else:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/'
else:
    # Local storage (development)
    MEDIA_URL = env('MEDIA_URL', default='/media/')
    MEDIA_ROOT = env('MEDIA_ROOT', default=os.path.join(BASE_DIR, 'media'))

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Use custom user model to allow future extensibility
AUTH_USER_MODEL = 'accounts.User'

# Django REST Framework & JWT (SimpleJWT)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.RedisJWTAuthentication',  # Use Redis-based JWT auth
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'google_auth': '10/minute',
        'password_reset_request': '5/hour',
        'password_reset_confirm': '20/hour',
        'password_reset_validate': '30/hour',
        'anon': '100/minute',
        'user': '1000/minute',
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,  # Temporarily disable for testing
    'BLACKLIST_AFTER_ROTATION': False,  # Temporarily disable for testing
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
}

# ---------------------------------------------------------------------------
# Email (Gmail SMTP and other providers)
# ---------------------------------------------------------------------------
# Prefer TLS on port 587 for Gmail. Alternative: EMAIL_USE_SSL=true, EMAIL_PORT=465.
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=30)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'webmaster@localhost')
SERVER_EMAIL = env('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)

# Public base URL for password-reset links in emails (SPA or API gateway). If empty, the
# request host is used when the reset is triggered via the API.
PASSWORD_RESET_PUBLIC_BASE_URL = env('PASSWORD_RESET_PUBLIC_BASE_URL', default='').rstrip('/')

# Frontend URL used to generate password reset links for users.
# Example: https://app.example.com
FRONTEND_URL = env('FRONTEND_URL', default=PASSWORD_RESET_PUBLIC_BASE_URL).rstrip('/')

# Django built-in token validity (seconds). Must match what you tell users in the email.
PASSWORD_RESET_TIMEOUT = env.int('PASSWORD_RESET_TIMEOUT', default=60 * 15)

# Staff-only POST /api/auth/email/test/ when True (never enable on public production without care)
ENABLE_EMAIL_TEST_API = env.bool('ENABLE_EMAIL_TEST_API', default=False)

# Cache configuration (defaults to in-memory for easy local testing)
# Set USE_LOC_MEM_CACHE=0 to use Redis via REDIS_URL in dev/prod
REDIS_URL = env('REDIS_URL', default='redis://127.0.0.1:6379/1')
if env.bool('USE_LOC_MEM_CACHE', default=(DJANGO_ENV == 'development')):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-coreapi-dev',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }

# Use Redis for JWT blacklist
SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'] = env.bool('JWT_BLACKLIST_AFTER_ROTATION', default=True)
SIMPLE_JWT['ROTATE_REFRESH_TOKENS'] = env.bool('JWT_ROTATE_REFRESH_TOKENS', default=True)

# ---------------------------------------------------------------------------
# Google Sign-In (ID token verification via google-auth)
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID', default='').strip()
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_PROJECT_ID = env('GOOGLE_PROJECT_ID', default='')


def _split_google_client_ids(raw: str) -> list[str]:
    """Support comma- or newline-separated client IDs in GOOGLE_CLIENT_ID."""
    if not raw:
        return []
    parts = raw.replace('\n', ',').split(',')
    return [p.strip() for p in parts if p.strip()]


_google_audiences: list[str] = []
_google_audiences.extend(_split_google_client_ids(GOOGLE_CLIENT_ID))
for _legacy_key in ('GOOGLE_WEB_CLIENT_ID', 'GOOGLE_ANDROID_CLIENT_ID', 'GOOGLE_IOS_CLIENT_ID'):
    _cid = env(_legacy_key, default='').strip()
    if _cid and _cid not in _google_audiences:
        _google_audiences.append(_cid)

GOOGLE_OAUTH2_ALLOWED_AUDIENCES = _google_audiences
# Backwards-compatible name used by older code / docs
GOOGLE_CLIENT_IDS = list(_google_audiences)

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

# ---------------------------------------------------------------------------
# Logging (includes SMTP / mail diagnostics)
# ---------------------------------------------------------------------------
LOG_LEVEL = env('LOG_LEVEL', default='INFO')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
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
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.core.mail': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'accounts.email_service': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}