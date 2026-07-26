import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env for local development
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────────────────────────
# In production SECRET_KEY is set via the Render environment variable.
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-dairy-management-secret-key-2024-local-only'
)

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    # Render — set via environment variable so any subdomain works
    # e.g. https://power-dairies.onrender.com
] + [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Required when running behind Render's / any HTTPS proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Project apps
    'accounts',
    'admin_app',
    'collector_app',
    'farmer_app',
    'mpesa',
    'chatbot',
]

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dairy_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dairy_management.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
# Render (and any other host) injects DATABASE_URL — use it when present.
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ['DATABASE_URL'],
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # Local development — SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Nairobi'
USE_I18N      = True
USE_TZ        = True

# ── Static & media files ──────────────────────────────────────────────────────
STATIC_URL      = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT     = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise — serves static files efficiently in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Authentication ────────────────────────────────────────────────────────────
LOGIN_URL           = 'accounts:login'
LOGIN_REDIRECT_URL  = 'accounts:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ── Email (console backend for now) ──────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Session ───────────────────────────────────────────────────────────────────
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE              = 3600
SESSION_SAVE_EVERY_REQUEST      = True
SESSION_COOKIE_HTTPONLY         = True

# Secure cookies — force True in production (when not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE    = not DEBUG

# ── M-Pesa Daraja API ─────────────────────────────────────────────────────────
_mpesa_env = os.environ.get('MPESA_ENVIRONMENT', 'sandbox').lower()
MPESA_CONFIG = {
    'SANDBOX':             _mpesa_env != 'production',
    'CONSUMER_KEY':        os.environ.get('MPESA_CONSUMER_KEY', ''),
    'CONSUMER_SECRET':     os.environ.get('MPESA_CONSUMER_SECRET', ''),
    'SHORTCODE':           os.environ.get('MPESA_SHORTCODE', '174379'),
    'PASSKEY':             os.environ.get('MPESA_PASSKEY', ''),
    'INITIATOR_NAME':      os.environ.get('MPESA_INITIATOR_NAME', 'testapi'),
    'SECURITY_CREDENTIAL': os.environ.get('MPESA_SECURITY_CREDENTIAL', ''),
    'C2B_SHORTCODE':       os.environ.get('MPESA_SHORTCODE', '174379'),
    'C2B_SHORT_CODE':      os.environ.get('MPESA_SHORTCODE', '174379'),
    'CALLBACK_URL':        os.environ.get('MPESA_CALLBACK_URL', ''),
    'ACCOUNT_REFERENCE':   os.environ.get('MPESA_ACCOUNT_REFERENCE', 'Power Dairies'),
    'TRANSACTION_DESC':    os.environ.get('MPESA_TRANSACTION_DESC', 'Payment for feed order'),
}
