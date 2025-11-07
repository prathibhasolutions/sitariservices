import os,environ
from pathlib import Path


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Use django-environ to read environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Security key from environment (keep secret)
SECRET_KEY = env('DJANGO_SECRET_KEY')

# Set debug to False for production
DEBUG = True

# Allowed hosts include your instance IP and domain
ALLOWED_HOSTS = ['65.0.89.209', 'localhost', '127.0.0.1', 'work.sitarisolutions.in', 'www.work.sitarisolutions.in']

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'dal',
    'dal_select2',
    'daterangefilter',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'management',
    'widget_tweaks',
    
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'management.ip_restriction.RestrictIPMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'management.context_processors.notifications_context',
                'management.context_processors_renewal.renewal_alerts_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'

# Database configuration (SQLite here; can be replaced by PostgreSQL or others)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    
]

# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Directory where collectstatic will collect static files for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Include your static source folders for development convenience
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Session security
SESSION_COOKIE_SECURE = False  # Set to True after SSL setup
CSRF_COOKIE_SECURE = False     # Set to True after SSL setup


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


JAZZMIN_SETTINGS = {
    # Title on the brand, and login screen (19 chars max)
    "site_header": "Sitari Solutions",
    "site_brand": "Sitari Solutions",

    # Logo to use for your site, must be present in static files
    "site_logo": "img/logo.jpg",

    # Logo to use for your site on the login screen, must be present in static files
    "login_logo": "img/logo.jpg",

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",

    # Welcome text on the login screen
    "welcome_sign": "Welcome to Sitari Solutions Admin",

    # Copyright on the footer
    "copyright": "Sitari Solutions Ltd",

    "custom_css": "css/jazzmin_custom.css",
}

