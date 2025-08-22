import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse, parse_qsl
import ssl
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

# Load env from project root and backend folder for local dev
if load_dotenv is not None:
    try:
        load_dotenv(BASE_DIR.parent / ".env", override=True)
        load_dotenv(BASE_DIR / ".env", override=True)
    except Exception:
        pass

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
if RENDER_EXTERNAL_URL:
    try:
        parsed_render = urlparse(RENDER_EXTERNAL_URL)
        if parsed_render.hostname and parsed_render.hostname not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(parsed_render.hostname)
    except Exception:
        pass

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.linkedin_oauth2",
    "dj_rest_auth",
    "dj_rest_auth.registration",

    # Local
    "api",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "resumeai.urls"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email", "openid"],
        "AUTH_PARAMS": {"access_type": "offline", "prompt": "consent"},
        # Optional: restrict to workspace domain
        # "HD": "yourcompany.com",
    },
    "linkedin_oauth2": {
        "SCOPE": ["r_liteprofile", "r_emailaddress"],
        "PROFILE_FIELDS": ["id", "localizedFirstName", "localizedLastName"],
    },
}

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

WSGI_APPLICATION = "resumeai.wsgi.application"

USE_SQLITE = os.getenv("USE_SQLITE", "True") == "True"
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "60"))
POSTGRES_SSLMODE = os.getenv("POSTGRES_SSLMODE", "require")

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Prefer DATABASE_URL if provided (e.g., Neon/Supabase):
    # Example: postgresql://user:pass@host:5432/dbname?sslmode=require
    database_url = os.getenv("DATABASE_URL", "").strip()
    # Be resilient to values copied with surrounding quotes
    if (database_url.startswith("'") and database_url.endswith("'")) or (
        database_url.startswith('"') and database_url.endswith('"')
    ):
        database_url = database_url[1:-1].strip()
    if database_url:
        try:
            parsed = urlparse(database_url)
            db_name = (parsed.path or "/").lstrip("/")
            options = dict(parse_qsl(parsed.query or ""))
            # Ensure sslmode is present (Neon/Supabase require TLS)
            options.setdefault("sslmode", POSTGRES_SSLMODE)

            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": db_name,
                    "USER": parsed.username,
                    "PASSWORD": parsed.password,
                    "HOST": parsed.hostname,
                    "PORT": parsed.port or os.getenv("POSTGRES_PORT", "5432"),
                    "CONN_MAX_AGE": DB_CONN_MAX_AGE,
                    "OPTIONS": options,
                }
            }
        except Exception:
            # Fallback to discrete POSTGRES_* env vars if parsing fails
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": os.getenv("POSTGRES_DB", "resumeai"),
                    "USER": os.getenv("POSTGRES_USER", "resumeai"),
                    "PASSWORD": os.getenv("POSTGRES_PASSWORD", "resumeai"),
                    "HOST": os.getenv("POSTGRES_HOST", "localhost"),
                    "PORT": os.getenv("POSTGRES_PORT", "5432"),
                    "CONN_MAX_AGE": DB_CONN_MAX_AGE,
                    "OPTIONS": {"sslmode": POSTGRES_SSLMODE},
                }
            }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("POSTGRES_DB", "resumeai"),
                "USER": os.getenv("POSTGRES_USER", "resumeai"),
                "PASSWORD": os.getenv("POSTGRES_PASSWORD", "resumeai"),
                "HOST": os.getenv("POSTGRES_HOST", "localhost"),
                "PORT": os.getenv("POSTGRES_PORT", "5432"),
                "CONN_MAX_AGE": DB_CONN_MAX_AGE,
                "OPTIONS": {"sslmode": POSTGRES_SSLMODE},
            }
        }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Proxy/HTTPS handling (important for correct OAuth redirect_uri on Render)
# Trust X-Forwarded-Proto from the proxy so request.is_secure() is accurate.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# When behind a proxy, allow Django to use X-Forwarded-Host for absolute URLs.
USE_X_FORWARDED_HOST = True
# Ensure allauth defaults to https for generated URLs when scheme is ambiguous.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
# Optional: enable strict HTTPS redirects in production via env flag.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").strip().lower() in {"1", "true", "yes", "on"}
# Secure cookies by default (can be relaxed locally by env flags if needed).
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").strip().lower() in {"1", "true", "yes", "on"}
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True").strip().lower() in {"1", "true", "yes", "on"}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # Persist exceptions via custom handler
    "EXCEPTION_HANDLER": "api.exception_handler.custom_exception_handler",
}

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")

# allauth basics
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
# Using default Django User model which includes 'username' field
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
# Socialaccount behavior tweaks for SPA
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_ALLOW_SIGNUPS = True
# Frontend/base URL to redirect to after login/logout/email confirmation
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# After successful login (including social), redirect to SPA dashboard
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL", f"{FRONTEND_URL}/dashboard")

# After logout, send users back to SPA login
ACCOUNT_LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL", f"{FRONTEND_URL}/login")

# Email confirmation redirects (optional)
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = os.getenv(
    "EMAIL_CONFIRMATION_ANON_REDIRECT_URL", f"{FRONTEND_URL}/login"
)
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = os.getenv(
    "EMAIL_CONFIRMATION_AUTH_REDIRECT_URL", f"{FRONTEND_URL}/dashboard"
)

# Skip intermediate confirmation screen for social login flows
SOCIALACCOUNT_LOGIN_ON_GET = True
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# Use a custom adapter to redirect back to the SPA with JWT tokens
SOCIALACCOUNT_ADAPTER = "api.adapters.CustomSocialAccountAdapter"
ACCOUNT_ADAPTER = "api.adapters.CustomAccountAdapter"

# dj-rest-auth / JWT
REST_USE_JWT = True
from datetime import timedelta  # noqa: E402
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Auto-extend CSRF trusted origins with Render external URL/hostname
_render_url = os.getenv("RENDER_EXTERNAL_URL")
if _render_url:
    try:
        _p = urlparse(_render_url)
        if _p.scheme and _p.hostname:
            _origin = f"{_p.scheme}://{_p.hostname}"
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)
    except Exception:
        pass
elif RENDER_EXTERNAL_HOSTNAME:
    _origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

# Auto-extend CORS/CSRF with production frontend origins
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    try:
        _p = urlparse(_frontend_url)
        if _p.scheme and _p.hostname:
            _origin = f"{_p.scheme}://{_p.hostname}"
            if _p.port:
                _origin = f"{_origin}:{_p.port}"
            if _origin not in CORS_ALLOWED_ORIGINS:
                CORS_ALLOWED_ORIGINS.append(_origin)
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)
    except Exception:
        pass

# Common Vercel env exposes domain without scheme
_vercel_url = os.getenv("VERCEL_URL")
if _vercel_url:
    try:
        _origin = f"https://{_vercel_url.strip()}"
        if _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)
    except Exception:
        pass

# Allow manual extra origins via comma-separated env
_extra = os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra:
    for _o in [o.strip() for o in _extra.split(",") if o.strip()]:
        if _o not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_o)
        if _o not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_o)

# Celery
# Prefer explicit CELERY_* vars, then REDIS_URL, then default localhost
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_DISABLE_RESULT_BACKEND = os.getenv("CELERY_DISABLE_RESULT_BACKEND", "False").strip().lower() in {"1", "true", "yes", "on"}

# Run tasks eagerly (synchronously) when no worker is available.
# Enable by setting env var CELERY_TASK_ALWAYS_EAGER=true (recommended on Render free tier).
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").strip().lower() in {"1", "true", "yes", "on"}
# Propagate exceptions to the caller when running eagerly.
CELERY_TASK_EAGER_PROPAGATES = os.getenv("CELERY_TASK_EAGER_PROPAGATES", "True").strip().lower() in {"1", "true", "yes", "on"}

# Ensure worker retries connecting to broker during startup (useful if Redis is initializing)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = os.getenv("CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP", "True").strip().lower() in {"1", "true", "yes", "on"}

# If using TLS Redis (rediss://), configure SSL requirements.
if str(CELERY_BROKER_URL).startswith("rediss://") or str(CELERY_RESULT_BACKEND).startswith("rediss://"):
    # Env override: NONE (default), OPTIONAL, REQUIRED
    cert_mode = os.getenv("REDIS_SSL_CERT_REQS", "NONE").strip().upper()
    _CERT_MAP = {
        "NONE": ssl.CERT_NONE,
        "OPTIONAL": ssl.CERT_OPTIONAL,
        "REQUIRED": ssl.CERT_REQUIRED,
    }
    cert_reqs = _CERT_MAP.get(cert_mode, ssl.CERT_NONE)
    # Celery/Kombu config
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": cert_reqs}
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": cert_reqs}

# Celery worker tuning (env-driven)
# Limit prefetch to reduce memory and improve fairness on small instances
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "4"))
# Auto-expire task results to keep memory/Redis usage low (seconds)
CELERY_RESULT_EXPIRES = int(os.getenv("CELERY_RESULT_EXPIRES", "3600"))
# Recycle worker processes periodically to mitigate leaks (lower = less memory growth, more respawns)
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "0"))  # 0 means disabled
# Limit broker connection pool to avoid too many sockets on tiny instances
CELERY_BROKER_POOL_LIMIT = int(os.getenv("CELERY_BROKER_POOL_LIMIT", "10"))
# If your app doesn't need Celery to store task return values, ignore results to reduce Redis usage
CELERY_TASK_IGNORE_RESULT = os.getenv("CELERY_TASK_IGNORE_RESULT", "False").lower() in {"1", "true", "yes"}

# If explicitly disabled, remove result backend and always ignore results
if CELERY_DISABLE_RESULT_BACKEND:
    CELERY_RESULT_BACKEND = None
    CELERY_TASK_IGNORE_RESULT = True

# File storage mode
FILE_STORAGE_MODE = os.getenv("FILE_STORAGE_MODE", "db")
