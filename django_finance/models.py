from django_base.models import *


class Bank(EntityModel):
    """ 账户（开户行）
    """

    code = models.CharField(
        verbose_name='银行编码',
        max_length=20,
        # unique=True,
    )

    pinyin = models.CharField(
        verbose_name='银行名称拼音',
        max_length=100,
    )

    class Meta:
        verbose_name = '银行'
        verbose_name_plural = '银行'
        db_table = 'core_finance_bank'

    @staticmethod
    def from_account(account):
        import json
        from urllib.request import urlopen
        from urllib.parse import quote_plus
        resp = urlopen(r'https://ccdcapi.alipay.com/validateAndCacheCardInfo.json' +
                       r'?cardNo={}&cardBinCheck=true'.format(quote_plus(account)))
        result = json.loads(resp.read().decode())
        return Bank.objects.filter(code=result.get('bank')).first()

    def save(self, *args, **kwargs):
        from uuslug import slugify
        self.pinyin = slugify(self.name)
        super().save(*args, **kwargs)




class BankAccount(UserOwnedModel,
                  EntityModel):
    """ 用户账号/银行账号/银行卡
    """

    bank = models.ForeignKey(
        verbose_name='开户行',
        to='Bank',
        related_name='accounts',
    )

    holder_name = models.CharField(
        verbose_name='开户人',
        max_length=40,
    )

    number = models.CharField(
        verbose_name='账号',
        max_length=50,
        unique=True,
    )

    is_default = models.BooleanField(
        verbose_name='是否默认',
        default=False,
    )

    class Meta:
        verbose_name = '用户账号'
        verbose_name_plural = '用户账号'
        db_table = 'core_finance_bank_account'

    def __str__(self):
        return '{}/{}/{}'.format(
            self.bank.name,
            self.number,
            self.holder_name,
        )


class PaymentRecord(UserOwnedModel):
    """ 抽象支付模型，用于记录支付平台的交易订单
    """

    PLATFORM_BALANCE = 'BALANCE'
    PLATFORM_WXPAY = 'WXPAY'
    PLATFORM_ALIPAY = 'ALIPAY'
    PLATFORM_IN_APP = 'APP'
    PLATFORM_PAYPAL = 'PAYPAL'
    PLATFORM_CHOICES = (
        (PLATFORM_BALANCE, '余额支付'),
        (PLATFORM_ALIPAY, '支付宝'),
        (PLATFORM_WXPAY, '微信支付'),
        (PLATFORM_IN_APP, 'Buy in app'),
        (PLATFORM_PAYPAL, 'Paypal'),
    )

    platform = models.CharField(
        verbose_name='支付平台',
        max_length=20,
        choices=PLATFORM_CHOICES,
        blank=True,
        default='',
    )

    out_trade_no = models.CharField(
        verbose_name='外部订单号',
        max_length=45,
    )

    amount = models.DecimalField(
        verbose_name='支付金额',
        decimal_places=2,
        max_digits=18,
    )

    subject = models.CharField(
        verbose_name='订单标题',
        max_length=255,
    )

    description = models.CharField(
        verbose_name='订单内容',
        max_length=255,
        blank=True,
        default='',
    )

    status = models.CharField(
        verbose_name='订单状态',
        max_length=45,
        blank=True,
        default='',
    )

    seller_id = models.CharField(
        verbose_name='商户ID',
        max_length=255,
        blank=True,
        default='',
    )

    seller_email = models.CharField(
        verbose_name='商户email',
        max_length=255,
        blank=True,
        default='',
    )

    buyer_id = models.CharField(
        verbose_name='买家ID',
        max_length=255,
        blank=True,
        default='',
    )

    date_created = models.DateTimeField(
        verbose_name='创建时间',
        auto_now_add=True,
    )

    date_notify = models.DateTimeField(
        verbose_name='回调时间',
        null=True,
        blank=True,
    )

    notify_data = models.TextField(
        verbose_name='完整回调数据',
        blank=True,
        default='',
    )

    payment_transaction = models.ForeignKey(
        verbose_name='支付产生余额增加的流水',
        to='AccountTransaction',
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = '支付记录'
        verbose_name_plural = '支付记录'
        db_table = 'core_finance_payment_record'

    def __str__(self):
        return '{} - {} - {}'.format(self.platform, self.author, self.out_trade_no)

    # def get_payment_url(self):
    #     try:
    #         if self.platform == self.PLATFORM_ALIPAY:
    #             return u.alipay_sign_url(
    #                 self.subject,
    #                 self.out_trade_no,
    #                 self.amount,
    #                 self.description,
    #                 self.date_created,
    #             )
    #     except Exception as e:
    #         pass
    #     return ''

    @staticmethod
    def get_serial(prefix):
        return '{}{}{:06d}'.format(
            prefix,
            datetime.now().strftime('%Y%m%d%H%M%S'),
            random.randint(0, 999999)
        )

    @staticmethod
    def notify(data):
        """
        传入支付平台的回调对象，然后找到订单验证变更其状态
        :param data:
        :return:
        """
        from urllib.parse import quote, unquote
        from django.conf import settings
        from base64 import b64decode, b64encode
        record = PaymentRecord.objects.filter(
            out_trade_no=data.get('out_trade_no')
        ).first()

        if record.platform == PaymentRecord.PLATFORM_ALIPAY:
            # print(get_request().POST)
            # 已经支付成功过
            if record.status in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
                return record

            # https://doc.open.alipay.com/docs/doc.htm?spm=a219a.7629140.0.0.KuaIia&treeId=203&articleId=105286&docType=1#s6
            assert u.alipay_verify(data), '验签失败'
            assert record, '系统订单号不存在'
            assert data.get('total_amount') == '{:.2f}'.format(record.amount), '金额不符'
            assert data.get('seller_id') == settings.ALIPAY_PARTNER, '商户号不匹配'
            assert data.get('app_id') == settings.ALIPAY_APP_ID, 'APP_ID不匹配'

            # 支付成功
            if data.get('trade_status') in ('TRADE_SUCCESS', 'TRADE_FINISHED'):

                # 记录回调过来的记录内容
                record.status = data.get('trade_status') or ''
                record.date_notify = datetime.now()
                record.notify_data = json.dumps(data)
                for k, v in data.items():
                    if hasattr(record, k):
                        setattr(record, k, v)
                record.save()
            else:
                return False

        elif record.platform == PaymentRecord.PLATFORM_WXPAY:

            # 已经支付成功过
            if record.status == 'SUCCESS':
                return record

            # https://doc.open.alipay.com/docs/doc.htm?spm=a219a.7629140.0.0.KuaIia&treeId=203&articleId=105286&docType=1#s6
            # assert u.alipay_verify(data), '验签失败'
            assert record, '系统订单号不存在'
            assert int(data.get('total_fee')) == int(100 * record.amount), '金额不符'
            assert data.get('mch_id') == settings.WXPAY_MCH_ID, '商户号不匹配'
            assert data.get('appid') == settings.WXPAY_APP_ID, 'APP_ID不匹配'

            # 支付成功
            if data.get('result_code') == 'SUCCESS':
                # 记录回调过来的记录内容
                record.status = data.get('result_code') or ''
                record.notify_data = json.dumps(data)
                record.amount = '{:.2f}'.format(int(data.get('total_fee')) / 100)
                record.buyer_id = data.get('openid')
                record.date_notify = datetime.now()
                record.seller_id = data.get('mch_id')
                record.seller_email = data.get('appid')
                # for k, v in data.items():
                #     if hasattr(record, k):
                #         setattr(record, k, v)
                record.save()
            else:
                return False

        # 记录充值增加余额的流水
        if hasattr(record, 'recharge_record'):
            transaction_remark = '{}充值'.format(
                dict(PaymentRecord.PLATFORM_CHOICES).get(record.platform))
            transaction_type = AccountTransaction.TYPE_RECHARGE
        else:
            transaction_remark = '支付平台直接支付'
            transaction_type = AccountTransaction.TYPE_DIRECT_PAY
        record.payment_transaction = AccountTransaction.objects.create(
            user_credit=None,
            user_debit=record.author,
            amount=record.get_real_amount(),
            type=transaction_type,
            remark=transaction_remark,
        )
        record.save()

        # 充值支付
        if hasattr(record, 'recharge_record'):
            # 标记充值完成
            record.recharge_record.done()
        # 订单支付
        elif hasattr(record, 'order'):
            # 标记支付完成
            record.order.set_paid()
        # 广告积分充值
        if hasattr(record, 'advert_recharge_record'):
            # 标记充值完成
            record.advert_recharge_record.done()

        return record

    def make_wx_payment_url(self):
        from urllib.request import urlopen
        from urllib.parse import quote
        from django.conf import settings
        url = r'http://wx.easecloud.cn/make_order/{}/?body={}&total_fee={}&out_trade_no={}'.format(
            settings.WXPAY_APP_ID, quote(self.subject),
            int(self.amount * 100), self.out_trade_no,
        )
        resp = urlopen(url)
        data = resp.read()
        return data.decode()

    def make_alipay_payment_url(self):
        from urllib.request import urlopen
        from urllib.parse import quote
        from django.conf import settings
        url = r'http://wx.easecloud.cn/make_order/{}/?subject={}&total_amount={:.02f}&out_trade_no={}&method=app'.format(
            settings.ALIPAY_APP_ID, quote(self.subject),
            self.amount, self.out_trade_no,
        )
        resp = urlopen(url)
        data = resp.read()
        return data.decode()

    def get_real_amount(self):
        """
        由于如果 PAYMENT_DEBUG 为 True 的时候实际支付记录的金额不正确，用这个方法可以返回实际的金额
        :return:
        """
        # 充值支付
        if hasattr(self, 'recharge_record'):
            # 标记充值完成
            return self.recharge_record.amount
        # 订单支付
        elif hasattr(self, 'order'):
            # 标记支付完成
            return self.order.total_amount()
        # 广告积分充值
        if hasattr(self, 'advert_recharge_record'):
            # 标记充值完成
            return self.advert_recharge_record.amount
        return self.amount


class RechargeRecord(UserOwnedModel,
                     EntityModel):
    account_transaction = models.OneToOneField(
        verbose_name='充值流水',
        to='AccountTransaction',
        null=True,
        blank=True,
        related_name='recharge_record',
    )

    payment_record = models.OneToOneField(
        verbose_name='支付记录',
        to='PaymentRecord',
        related_name='recharge_record',
    )

    amount = models.DecimalField(
        verbose_name='充值金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    class Meta:
        verbose_name = '充值记录'
        verbose_name_plural = '充值记录'
        db_table = 'core_finance_recharge_record'

    @staticmethod
    def make_order(amount, author=None, platform=PaymentRecord.PLATFORM_ALIPAY):
        from django.conf import settings
        out_trade_no = 'RC{}{:06d}'.format(
            datetime.now().strftime('%Y%m%d%H%M%S'),
            random.randint(0, 999999)
        )
        payment_record = PaymentRecord.objects.create(
            author=author,
            platform=platform,
            amount='{:.2f}'.format(0.01 if settings.PAYMENT_DEBUG else amount),
            subject='充值',
            description='充值',
            out_trade_no=out_trade_no,
            seller_id=settings.ALIPAY_PARTNER,
        )
        return RechargeRecord.objects.create(
            author=author,
            amount='{:.2f}'.format(amount),
            payment_record=payment_record,
        )

    def done(self):
        """ 完成支付动作（写入财务流水） """
        self.account_transaction = self.payment_record.payment_transaction
        self.save()


class WithdrawRecord(UserOwnedModel,
                     EntityModel):
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = (
        (STATUS_PENDING, '申请中'),
        (STATUS_APPROVED, '提现成功'),
        (STATUS_REJECTED, '驳回'),
    )

    status = models.CharField(
        verbose_name='状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    date_approve = models.DateTimeField(
        verbose_name='审批时间',
        null=True,
        blank=True,
    )

    user_approve = models.ForeignKey(
        verbose_name='审核员',
        to=User,
        null=True,
        blank=True,
    )

    bank_account = models.ForeignKey(
        verbose_name='银行',
        to='BankAccount',
        related_name='withdraw_records',
    )

    amount = models.DecimalField(
        verbose_name='金额',
        max_digits=18,
        decimal_places=2,
    )

    account_transaction = models.OneToOneField(
        verbose_name='提现流水',
        to='AccountTransaction',
        related_name='withdraw_record',
        null=True,
        blank=True,
    )

    fee_rate = models.DecimalField(
        verbose_name='提现手续费率',
        max_digits=18,
        decimal_places=2,
        blank=True,
        default=0,
    )

    actual_amount = models.DecimalField(
        verbose_name='实际金额',
        max_digits=18,
        decimal_places=2,
        null=True,
    )

    class Meta:
        verbose_name = '提现记录'
        verbose_name_plural = '提现记录'
        db_table = 'core_finance_withdraw_record'

    @staticmethod
    def make(user, amount, bank_account):
        """ 申请一个提现 """
        balance = WithdrawRecord.check_balance(user)
        if amount > balance:
            raise ValidationError('提现额度超出限制')
        if bank_account and bank_account.author != user:
            raise ValidationError('提现账号的所有者与申请用户不符')
        # print(amount, bank_account)
        # 加入手续费百分比
        from decimal import Decimal
        fee_rate = Decimal(Option.get('withdraw_fee_rate') or 0)
        actual_amount = amount * (100 - fee_rate) / 100
        return WithdrawRecord.objects.create(
            author=user,
            bank_account=bank_account,
            amount=amount,
            fee_rate=fee_rate,
            actual_amount=actual_amount,
        )

    @staticmethod
    def check_balance(user):
        """ 返回一个用户可以提现的余额 """
        debit = user.accounttransactions_debit.aggregate(
            total=models.Sum('amount')).get('total') or 0
        credit = user.accounttransactions_credit.aggregate(
            total=models.Sum('amount')).get('total') or 0
        pending_amount = user.withdrawrecords_owned.filter(
            status=WithdrawRecord.STATUS_PENDING).aggregate(
            total=models.Sum('amount')).get('total') or 0
        return debit - credit - pending_amount

    def reject(self, user_approve=None):
        self.status = self.STATUS_REJECTED
        self.date_approve = datetime.now()
        self.user_approve = user_approve
        self.save()
        # 审核通过发送系统消息
        Message.objects.create(
            type='OBJECT',
            content='提现审批驳回-{}(****{}),金额 {}'.format(
                self.bank_account.bank.name,
                self.bank_account.number[-4:],
                self.amount,
            ),
            receiver=self.author,
        )
        return True

    def approve(self, user_approve=None):
        """ 审批一个提现 """
        if self.status != self.STATUS_PENDING:
            raise ValidationError('状态不正确')
        self.status = self.STATUS_APPROVED
        self.date_approve = datetime.now()
        self.user_approve = user_approve
        # 还要插入一条流水
        if not self.account_transaction:
            self.account_transaction = AccountTransaction.objects.create(
                type=AccountTransaction.TYPE_WITHDRAW,
                user_debit=None,
                user_credit=self.author,
                amount=self.amount,
                remark='提现-{}(****{})'.format(
                    self.bank_account.bank.name,
                    self.bank_account.number[-4:]
                )
            )
        self.save()
        # 审核通过发送系统消息
        Message.objects.create(
            type='OBJECT',
            content='提现审批通过-{}(****{}),金额 {}'.format(
                self.bank_account.bank.name,
                self.bank_account.number[-4:],
                self.amount,
            ),
            receiver=self.author,
            params=json.dumps(dict(
                action='withdraw_approve',
                account=self.account_transaction.id,
            ))
        )
        return True


class AccountTransaction(HierarchicalModel,
                         AbstractTransactionModel,
                         EntityModel):
    """ 资金流水
    这里使用了 HierarchicalModel 的层级构造，也就是说流水具备 parent 属性
    是这样考虑的，可能有些操作涉及手续费，抽佣等操作，
    这样的话，我们将手续费的流水的 parent 设置为被抽佣的流水，以记录关联。
    """

    TYPE_RECHARGE = 'RECHARGE'
    TYPE_WITHDRAW = 'WITHDRAW'
    TYPE_COMMISSION = 'COMMISSION'
    TYPE_PURCHASE = 'PURCHASE'
    TYPE_FEE = 'FEE'
    TYPE_REFUND = 'REFUND'
    TYPE_DIRECT_PAY = 'DIRECT_PAY'
    TYPE_CHOICES = (
        (TYPE_RECHARGE, '充值'),
        (TYPE_WITHDRAW, '提现'),
        (TYPE_COMMISSION, '佣金'),
        (TYPE_PURCHASE, '消费'),
        (TYPE_FEE, '手续费'),
        (TYPE_REFUND, '退款'),
        (TYPE_DIRECT_PAY, '直接支付'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '财务流水'
        verbose_name_plural = '财务流水'
        db_table = 'core_finance_account_transaction'



