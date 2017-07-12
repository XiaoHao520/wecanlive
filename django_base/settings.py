import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

SECRET_KEY = 'SIMPLE_SECRET_KEY_DO_NOT_USE_IN_PRODUCTION'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Included third-party apps
    'corsheaders',
    'django_fullclean',
    'rest_framework',
    'django_filters',
    # Project app
    'django_base',
]

MIDDLEWARE = [
    'django_base.middleware.CustomExceptionMiddleware',
    'django_base.middleware.GlobalRequestMiddleware',
    'django_base.middleware.FullMediaUrlMiddleware',
    'django_base.middleware.DebugMiddleware',
    'django_base.middleware.CookieCsrfMiddleware',
    'django_base.middleware.GlobalRequestMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'django_wecanlive',
        'USER': 'root',
        'PASSWORD': 'root',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': '''
            SET default_storage_engine=INNODB;
            SET sql_mode='STRICT_TRANS_TABLES';
            ''',
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_general_ci',
        },
    },
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    # }
}


# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# =========== REST Framework ==============
REST_FRAMEWORK = {
    'PAGE_SIZE': 10,
    # 'DEFAULT_PAGINATION_CLASS':
    #     'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_PAGINATION_CLASS':
        'django_base.paginations.CustomPagination',
    'DEFAULT_FILTER_BACKENDS': (
        # 'rest_framework_filters.backends.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
        # 'core.filters.RelatedOrderingFilter',
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    # 'DEFAULT_RENDERER_CLASSES': (
    #     # 'rest_framework.renderers.JSONRenderer',
    #     'rest_framework.renderers.BrowsableAPIRenderer',
    # ),
    'DATE_FORMAT': '%Y-%m-%d',
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'COERCE_DECIMAL_TO_STRING': False,
    # 'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# =========== CORS ===============

# CORS_ORIGIN_ALLOW_ALL = DEBUG
CORS_ORIGIN_REGEX_WHITELIST = r'.*'
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = ['null', '.local']

# ============== Payment ===============

# 如果开启调试，所有实际支付的金额会变成 1 分钱
PAYMENT_DEBUG = True

# ============== Models ==============

# 是否开启假删除
PSEUDO_DELETION = True

# 是否自动开启地理信息反解
AUTO_GEO_DECODE = True

# 百度地图 API_KEY
BMAP_KEY = 'D373d23acd37b0c4af370a517922e020'

# 是否将音频自动转换为 ogg/mp3
NORMALIZE_AUDIO = True

# =============== Tencent MLVB ==============

# 騰訊移動直播
# bizId 編號（4位數字）
TENCENT_MLVB_BIZ_ID = '9857'
TENCENT_MLVB_APPID = '1253850554'
# 推流防盜鏈 Key
TENCENT_MLVB_PUSH_KEY = 'd2f7f1ba70d87e6f58751fbc17427cb8'
# API鑑權 Key
TENCENT_MLVB_API_AUTH_KEY = '90c0bc75580a4e91b767e216de99bfbc'
