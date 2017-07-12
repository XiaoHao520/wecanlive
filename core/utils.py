import re
import random
import json
from time import time
from datetime import datetime
from calendar import monthrange

from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA

import base64
from base64 import b64decode, b64encode

from django.core.exceptions import ValidationError
from django.shortcuts import Http404
from django.conf import settings

from rest_framework.response import Response


# def rsa_sign(text):
#     key = RSA.importKey(b64decode(settings.ALIPAY_RSA_PRIVATE))
#     h = SHA.new(text.encode())
#     signer = PKCS1_v1_5.new(key)
#     return b64encode(signer.sign(h)).decode()
#
#
# def rsa_verify(text, sign):
#     from base64 import b64decode, b64encode
#     public_key = RSA.importKey(b64decode(settings.ALIPAY_RSA_PUBLIC))
#     sign = b64decode(sign)
#     h = SHA.new(text.encode('GBK'))
#     verifier = PKCS1_v1_5.new(public_key)
#     return verifier.verify(h, sign)
#
#
# def alipay_verify(data):
#     # QueryDict 转 Dict
#     data = {k: data[k] for k in data}
#     print(data)
#     sign = data.pop('sign')
#     print(sign)
#     data.pop('sign_type')
#     text = '&'.join(['='.join(item) for item in sorted(data.items())])
#     return rsa_verify(text, sign or data.get('sign') + '')
#
#
# def alipay_sign_url(subject, out_trade_no, total_amount, body='', timestamp=None):
#     args = dict(
#         app_id=settings.ALIPAY_APP_ID,
#         method='alipay.trade.wap.pay',
#         charset='utf-8',
#         sign_type='RSA',
#         timestamp=(timestamp or datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
#         version='1.0',
#         notify_url=settings.ALIPAY_NOTIFY_URL,
#         return_url=settings.ALIPAY_RETURN_URL,
#         biz_content=json.dumps(dict(
#             body=body,
#             subject=subject,
#             out_trade_no=out_trade_no,
#             total_amount='{:.2f}'.format(total_amount),
#             product_code='QUICK_WAP_PAY',
#         )),
#     )
#
#     order_info = '&'.join(['{}={}'.format(k, v) for k, v in sorted(args.items())])
#     return '{}&sign={}'.format(order_info, rsa_sign(order_info))


def response_success(msg=''):
    return Response(data=dict(
        ok=True,
        msg=msg,
    ))


def response_fail(msg='', error_code=0, status=400):
    return Response(data=dict(
        ok=False,
        error_code=error_code,
        msg=msg,
    ), status=status)


def sanitize_mobile(mobile):
    """ 过滤手机号码
    如果手机号码格式符合要求，直接返回
    否则抛出 ValidationError
    :param mobile:
    :return:
    """
    assert re.match(r'^1[3-9]\d{9}$', mobile), '手机号码格式不正确'
    return mobile


def sanitize_password(password):
    """
    :param password:
    :return:
    """
    assert len(password) >= 6, '密码长度不得低于 6 位'
    return password


def require_mobile_vcode(view_func):
    """ Decorator 要求 post 中提供 Session 中产生的验证码
    :return:
    """

    def _wrapped_view(self, request, *args, **kwargs):
        # 要求输入/传入的手机验证码
        vcode_sent = request.data.get('mobile_vcode')
        vcode_info = get_vcode_info(request)

        if not vcode_sent \
                or not vcode_info \
                or vcode_sent != vcode_info.get('vcode'):
            return response_fail('驗證碼不正確！', 50001)

        resp = view_func(self, request, *args, **kwargs)

        # 验证成功马上擦除
        clear_vcode_info(request)

        return resp

    return _wrapped_view


def clear_vcode_info(request):
    request.session['mobile_vcode_number'] = ''
    request.session['mobile_vcode'] = ''
    request.session['mobile_vcode_time'] = 0


def set_vcode_info(request, mobile, vcode):
    request.session['mobile_vcode_number'] = mobile
    request.session['mobile_vcode'] = vcode
    request.session['mobile_vcode_time'] = int(time())


def get_vcode_info(request):
    # 上次请求验证码的时间
    last_sms_request_time = int(request.session.get('mobile_vcode_time', 0))

    # 验证码是否到期
    if time() > last_sms_request_time + settings.SMS_EXPIRE_INTERVAL:
        return None

    return dict(
        mobile=request.session['mobile_vcode_number'],
        vcode=request.session['mobile_vcode'],
    )


def request_mobile_vcode(request, mobile):
    """
    为传入的 request 上下文（Session）产生一个手机验证码，
    发送给指定的手机号码，并且记录在 session.mobile_vcode 中。
    :param request:
    :param mobile:
    :return:
    """

    mobile = sanitize_mobile(mobile)

    # 上次请求验证码的时间
    last_sms_request_time = int(request.session.get('mobile_vcode_time', 0))
    # 一分钟内不允许重发
    if time() < last_sms_request_time + settings.SMS_SEND_INTERVAL:
        raise ValidationError(
            '您的操作过于频繁，请在 %d 秒后再试。'
            % (last_sms_request_time + settings.SMS_SEND_INTERVAL - time()))

    vcode = '%06d' % (random.randint(0, 1000000))
    # 如果开启了调试选项，不真正发送短信
    if not settings.SMS_DEBUG:
        sms_send(
            mobile,
            settings.SMS_TEMPLATE_CODE.get('validate'),
            dict(code=vcode, product='注册'),
        )
    set_vcode_info(request, mobile, vcode)
    return vcode


def sms_send(mobile, template_code, params):
    mobile = sanitize_mobile(mobile)

    from alidayu import AlibabaAliqinFcSmsNumSendRequest

    # 发送手机短信
    req = AlibabaAliqinFcSmsNumSendRequest(
        settings.SMS_APPKEY,
        settings.SMS_SECRET
    )

    # req.extend = '123456'
    req.sms_type = "normal"
    req.sms_free_sign_name = settings.SMS_SIGN_NAME
    req.sms_param = json.dumps(params)
    req.rec_num = mobile
    req.sms_template_code = template_code

    # 检验发送成功与否并返回 True，失败的话抛一个错误
    resp = req.getResponse()

    if resp.get('error_response'):
        raise ValidationError(
            resp.get('error_response').get('msg'))

    return resp
    # try:
    #     resp = req.getResponse()
    #     request.session['mobile_vcode'] = vcode
    #     print(resp)
    # except Exception as e:
    #     print(e)


def normalize_date(dt):
    return datetime.strptime(dt, '%Y-%m-%d') if type(dt) == str else dt


def get_month_first_day(dt):
    dt = normalize_date(dt)
    return datetime(dt.year, dt.month, 1)


def get_month_last_day(dt):
    dt = normalize_date(dt)
    return datetime(dt.year, dt.month, monthrange(dt.year, dt.month)[1])


def get_year_first_day(dt):
    dt = normalize_date(dt)
    return datetime(dt.year, 1, 1)


def get_year_last_day(dt):
    dt = normalize_date(dt)
    return datetime(dt.year, 12, 31)


def get_quarter_first_day(dt):
    dt = normalize_date(dt)
    month = [0, 1, 1, 1, 4, 4, 4, 7, 7, 7, 10, 10, 10][dt.month]
    return datetime(dt.year, month, 1)


def get_quarter_last_day(dt):
    dt = normalize_date(dt)
    month = [0, 3, 3, 3, 6, 6, 6, 9, 9, 9, 12, 12, 12][dt.month]
    return datetime(dt.year, month, monthrange(dt.year, month)[1])
