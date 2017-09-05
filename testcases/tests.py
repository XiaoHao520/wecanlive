from django.test import TestCase
from urllib.request import urlopen
from urllib.parse import urljoin
from core.models import *
from time import time
from django.conf import settings
from hashlib import md5


# Create your tests here.
class WecanPaymentTestCase(TestCase):
    API_ROOT = 'http://127.0.0.1:8000/api/'

    def get_model_by_id(self, model, id):
        resp = urlopen(
            urljoin('{}{}/'.format(self.API_ROOT, model), '{}/'.format(id))
        )
        return json.loads(resp.read().decode())

    def test_01_payment_api(self):
        author = User.objects.order_by('?').first()
        data = dict(
            account='15913126494',
            serverid='1325646',
            platform='A',
            orderid=str(random.randint(0, 99999999)),
            productid='com.twwecan.live.item01',
            imoney=30,
            to_account='',
            extra='',
            time=int(time()),
        )
        str_to_hash = data.get('account') + data.get('platform') + data.get('orderid') + str(data.get('imoney')) + str(
            data.get('time')) + settings.WECAN_PAYMENT_VERIFY_KEY
        my_hash = md5(str_to_hash.encode()).hexdigest()
        data['verify'] = my_hash
        from urllib.parse import urlencode
        print(data)
        resp = urlopen(
            urljoin('{}{}'.format(self.API_ROOT, 'recharge_record/'), 'notify/'),
            data=urlencode(data).encode(),
        )
        body = json.loads(resp.read().decode())
        print(body)
        payment_record = self.get_model_by_id('payment_record', '?out_trade_no={}'.format(data.get('orderid')))
        assert body.get('code') == '0', '失败'
        assert payment_record, '创建支付记录失败'
        # assert payment_record.get('out_trade_no') == data.get('orderid'), '外部订单号不一致'
        recharge_record = self.get_model_by_id('recharge_record', '?payment_record={}'.format(payment_record.id))
        assert recharge_record, '创建充值订单失败'
        # assert self.get_model_by_id()


class WecanUserTestCase(TestCase):
    API_ROOT = 'http://127.0.0.1:8000/api/'

    # userid = ''
    # def setUpClass(cls):
    #     cls.userid = ...
    # def tearDownClass(cls):
    #     cls.userid = ...

    def test_01_query_user_api(self):
        author = User.objects.order_by('?').first()
        data = dict(
            account='13800138001',
            serverid='1325646',
            time=int(time()),
        )
        str_to_hash = data.get('account') + data.get('serverid') + str(
            data.get('time')) + settings.WECAN_PAYMENT_VERIFY_KEY
        my_hash = md5(str_to_hash.encode()).hexdigest()
        data['verify'] = my_hash
        from urllib.parse import urlencode
        resp = urlopen(
            urljoin('{}{}'.format(self.API_ROOT, 'user/'), 'query_user/'),
            data=urlencode(data).encode(),
        )
        body = json.loads(resp.read().decode())
        print(body)
        assert body.get('code') == '0', '失败'
