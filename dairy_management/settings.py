import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-dairy-management-secret-key-2024'

DEBUG = True

ALLOWED_HOSTS = ['*']
# CSRF trusted origins - Add your Railway URL
CSRF_TRUSTED_ORIGINS = [
    'https://power-dairies-management-production.up.railway.app',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# Tell Django it's behind a proxy (Railway uses HTTPS)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom Apps
    'accounts',
    'admin_app',
    'collector_app',
    'farmer_app',
    'mpesa',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this line
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Database - Use PostgreSQL in production
if os.environ.get('DATABASE_URL'):
    # Production (Railway)
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
    }
else:
    # Development (Local)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:dashboard'  # Where to go after successful login
LOGOUT_REDIRECT_URL = 'accounts:login'     # Where to go after logout
# Email settings for claims
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Session settings - Force login every time
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Session expires when browser closes
SESSION_COOKIE_AGE = 3600  # Session expires after 1 hour of inactivity (optional)
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session on every request

# Optional: Set session cookie to be more secure
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS in production
CSRF_COOKIE_SECURE = False

# M-Pesa Daraja API Configuration
MPESA_CONFIG = {
    'SANDBOX': True,  # Set to False for production
    'CONSUMER_KEY': 'YbTvHLd5umXel5IdYeGcjuBvEOtzXGqoZdLTFlwz3nmFnEPh',
    'CONSUMER_SECRET': 'jtblbRUPU2PrnVpJWj6XUtJshSfEvYoZL9Y7fQBC2TjUdQ7gRnNJTj72yDGoXjND',
    'SHORTCODE': '174379',  # Test shortcode for sandbox
    'PASSKEY': 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919',  # Sandbox passkey
    'INITIATOR_NAME': 'testapi',
    'SECURITY_CREDENTIAL': 'test_credential',
    'C2B_SHORTCODE': '174379',
    'C2B_SHORT_CODE': '174379',
    'CALLBACK_URL': 'https://sandpit-depth-squatting.ngrok-free.dev/mpesa/callback/', # Update with your domain
    'ACCOUNT_REFERENCE': 'Power Dairies',
    'TRANSACTION_DESC': 'Payment for feed order',
}