"""
Assured Express Logistics — Django Settings
"""
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")

# ── Applications ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
    "drf_spectacular",
    "django_celery_beat",
    # Internal apps
    "apps.authentication",
    "apps.core",
    "apps.comms",
    "apps.coach",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "assured_express.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "assured_express.wsgi.application"
ASGI_APPLICATION = "assured_express.asgi.application"

# ── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     config("DB_NAME",     default="assured_express"),
        "USER":     config("DB_USER",     default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST":     config("DB_HOST",     default="localhost"),
        "PORT":     config("DB_PORT",     default="5432"),
    }
}

# ── Cache / Channel Layers ───────────────────────────────────────────────────
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ── Auth ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "authentication.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ── JWT ─────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000,https://axpress-operations-command-center.vercel.app",
).split(",")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "https://metrics.axpress.net",
    "https://axpress-operations-command-center.vercel.app",
]

# ── Spectacular (OpenAPI docs) ───────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Assured Express Logistics API",
    "DESCRIPTION": "Operations Command Center — Riders, Merchants, Zones, Communications",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"

# ── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── AXpress Main Backend (service-to-service) ───────────────────────────────
AXPRESS_BASE_URL   = config("AXPRESS_BASE_URL",   default="http://localhost:8001")
AXPRESS_SERVICE_KEY = config("AXPRESS_SERVICE_KEY", default="")

# ── APEX AI Coach ────────────────────────────────────────────────────────────
COACH_LLM_PROVIDER     = config("COACH_LLM_PROVIDER",     default="anthropic")  # "anthropic" or "openai"
COACH_MODEL            = config("COACH_MODEL",            default="claude-sonnet-4-20250514")
COACH_ANTHROPIC_API_KEY = config("COACH_ANTHROPIC_API_KEY", default="")
COACH_OPENAI_API_KEY    = config("COACH_OPENAI_API_KEY",    default="")

# ── SMS / WhatsApp / Email providers ─────────────────────────────────────────
# Termii (Nigerian SMS/WhatsApp gateway)
TERMII_API_KEY    = config("TERMII_API_KEY",    default="")
TERMII_SENDER_ID  = config("TERMII_SENDER_ID",  default="AssuredExp")
TERMII_BASE_URL   = "https://api.ng.termii.com/api"

# SendGrid (Email)
SENDGRID_API_KEY  = config("SENDGRID_API_KEY",  default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="ops@assuredexpress.ng")

# Firebase (Rider in-app push)
FIREBASE_CREDENTIALS_JSON = config("FIREBASE_CREDENTIALS_JSON", default="")

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps":   {"handlers": ["console"], "level": "DEBUG",   "propagate": False},
    },
}
