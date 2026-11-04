"""Django settings for the NewsHub backend."""
from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env if present. Real environment variables win over the file.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-newshub-local-development-key")
if not DEBUG and (
    not os.getenv("DJANGO_SECRET_KEY")
    or SECRET_KEY.startswith("django-insecure")
    or any(marker in SECRET_KEY.lower() for marker in ("change-me", "replace-with", "your-secret"))
    or len(SECRET_KEY) < 32
):
    raise ImproperlyConfigured("Set a unique DJANGO_SECRET_KEY of at least 32 characters before running with DJANGO_DEBUG=false.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS before running with DJANGO_DEBUG=false.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "accounts",
    "news",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
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
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "newshub"),
            "USER": os.getenv("DB_USER", "newshub"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": {"connect_timeout": 10},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PAGINATION_CLASS": "news.pagination.StandardPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_THROTTLE_RATES": {
        "fact_check": "30/hour",
        "ai": "60/hour",
        "article_content": "30/hour",
        "reading": "240/hour",
        "auth": "20/hour",
    },
    "EXCEPTION_HANDLER": "news.exceptions.newshub_exception_handler",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "newshub-cache",
        "TIMEOUT": 600,
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "newshub": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# NewsHub application settings
# ---------------------------------------------------------------------------
NEWSHUB = {
    "FETCH_TIMEOUT": float(os.getenv("NEWS_FETCH_TIMEOUT", "8")),
    "CACHE_TTL": int(os.getenv("NEWS_CACHE_TTL", "600")),
    "FEED_MAX_ITEMS": int(os.getenv("NEWS_MAX_ARTICLES_PER_FEED", "35")),
    "LIVE_FETCH_ENABLED": env_bool("NEWS_ENABLE_LIVE_FETCH", True),
    "FRESHNESS_WINDOW_MINUTES": int(os.getenv("NEWS_FRESHNESS_MINUTES", "15")),
    "MAX_FEEDS": int(os.getenv("NEWS_MAX_FEEDS", "50")),
    # Primary/fallback text-generation providers (no SDK install required).
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "").strip(),
    "GEMINI_BASE_URL": os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ).strip(),
    "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
    "GEMINI_TIMEOUT": float(os.getenv("GEMINI_TIMEOUT", "18")),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", "").strip(),
    "GROQ_BASE_URL": os.getenv(
        "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
    ).strip(),
    "GROQ_MODEL": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
    "GROQ_TIMEOUT": float(os.getenv("GROQ_TIMEOUT", "18")),
    # On-demand publisher article extraction. Text is cached temporarily, not
    # written back to Article.content; robots.txt and publisher restrictions apply.
    "ARTICLE_EXTRACTION_ENABLED": env_bool("ARTICLE_EXTRACTION_ENABLED", True),
    "ARTICLE_EXTRACTION_RESPECT_ROBOTS": env_bool("ARTICLE_EXTRACTION_RESPECT_ROBOTS", True),
    "ARTICLE_EXTRACTION_TIMEOUT": float(os.getenv("ARTICLE_EXTRACTION_TIMEOUT", "9")),
    "ARTICLE_EXTRACTION_MAX_BYTES": int(os.getenv("ARTICLE_EXTRACTION_MAX_BYTES", str(3 * 1024 * 1024))),
    "ARTICLE_EXTRACTION_CACHE_TTL": int(os.getenv("ARTICLE_EXTRACTION_CACHE_TTL", "21600")),
    "ARTICLE_EXTRACTION_FAILURE_TTL": int(os.getenv("ARTICLE_EXTRACTION_FAILURE_TTL", "600")),
    # Legacy OpenAI-compatible provider: used only when Gemini/Groq are absent,
    # unless explicitly enabled as a third fallback.
    "LLM_API_KEY": os.getenv("LLM_API_KEY", "").strip(),
    "LLM_BASE_URL": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
    "LLM_MODEL": os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
    "LLM_TIMEOUT": float(os.getenv("LLM_TIMEOUT", "25")),
    "LLM_ENABLE_LEGACY_FALLBACK": env_bool("LLM_ENABLE_LEGACY_FALLBACK", False),
    "TRANSLATION_API_URL": os.getenv("TRANSLATION_API_URL", "").strip(),
    "TRANSLATION_API_KEY": os.getenv("TRANSLATION_API_KEY", "").strip(),
    "SARVAM_API_KEY": os.getenv("SARVAM_API_KEY", "").strip(),
    "SARVAM_TRANSLATE_API_URL": os.getenv("SARVAM_TRANSLATE_API_URL", "https://api.sarvam.ai/translate").strip(),
    "TRANSLATION_TIMEOUT": float(os.getenv("TRANSLATION_TIMEOUT", "25")),
    "NEWSAPI_KEY": os.getenv("NEWSAPI_KEY", "").strip(),
    "GNEWS_API_KEY": os.getenv("GNEWS_API_KEY", "").strip(),
    "USER_AGENT": "NewsHub/1.0 (educational news aggregation project)",
}

# ML artifacts are trained locally with `python manage.py train_classifier`.
ML_ARTIFACT_DIR = BASE_DIR / "news" / "ml" / "artifacts"
