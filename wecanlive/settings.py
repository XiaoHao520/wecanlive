from django_base.settings import *
from . import settings_params as params

SECRET_KEY = '034a6j^$%7^5qq%m=p2rqo_stevf6ndlx8_ff6%p=zl(#w2l5t'

DEBUG = True

ALLOWED_HOSTS = [
    'app.local',
    'app.local.easecloud.cn',
]

INSTALLED_APPS += [
    'django_member',
    'django_finance',
    'core',
]

MIDDLEWARE += [
]

WSGI_APPLICATION = 'wecanlive.wsgi.application'

DATABASES['default']['NAME'] = params.DB_NAME
DATABASES['default']['USER'] = params.DB_USER
DATABASES['default']['PASSWORD'] = params.DB_PASS
DATABASES['default']['HOST'] = params.DB_HOST
DATABASES['default']['PORT'] = params.DB_PORT

# =========== CRON =======================

CRON_CLASSES = [
    'core.cron.AutomaticShelvesCronJob',
]

# =============== SMS Config ===================

SMS_APPKEY = '23405490'
SMS_SECRET = 'fc4dde7fe3659364293bd830d334e3a4'
SMS_TEMPLATE_CODE = {'validate': 'SMS_12225993'}
SMS_SEND_INTERVAL = 10  # 短信发送时间间隔限制
SMS_EXPIRE_INTERVAL = 1800
SMS_SIGN_NAME = '注册验证'
SMS_DEBUG = False  # 不真正发送短信，将验证码直接返回

# ============== Payment ===============

# 如果开启调试，所有实际支付的金额会变成 1 分钱
PAYMENT_DEBUG = True

ALIPAY_NOTIFY_URL = 'http://app.hwc.easecloud.cn/api/payment_record/notify/'
ALIPAY_APP_ID = '2017020905592464'  # sandbox
ALIPAY_RSA_PUBLIC = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDDI6d306Q8fIfCOaTXyiUeJHkrIvYISRcc73s3vF1ZT7XN8RNPwJxo8pWaJMmvyTn9N4HQ632qJBVHf8sxHi/fEsraprwCtzvzQETrNRwVxLO5jVmRGi60j8Ue1efIlzPXV9je9mkjzOmdssymZkh2QhUrCmZYI/FCEa3/cNMW0QIDAQAB'
ALIPAY_PARTNER = '2088621141222290'


WXPAY_APP_ID = 'wx8d2476a16822f3a9'
WXPAY_APP_SECRET = 'eae9b4d0d288eb02aec6a946f463bcf4'
WXPAY_MCH_ID = '1438827302'
WXPAY_API_KEY = '65467qewrtg2e3v62v26cc8v26cvnmnj'
WXPAY_APICLIENT_CERT = ''
WXPAY_APICLIENT_KEY = ''
