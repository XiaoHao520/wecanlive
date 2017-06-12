import json
import os
import os.path
import random

from datetime import datetime, timedelta

from django.db import models
from django.conf import settings
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError

from . import utils as u
from .middleware import get_request


class AutoApproveModel(models.Model):
    """
    自动审批模型
    """

    date_auto_approve = models.DateTimeField(
        verbose_name='自动审批时间',
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        is_create = not self.pk
        # 获取对应模型的自动审批设置，如果为 0，不自动审批。
        # 如果为正数，则在对应分钟数之后自动审批
        setting_key = 'auto_approve_minutes_' + type(self).__name__.lower()
        auto_approve = int(Option.get(setting_key) or 0)
        if is_create:
            self.is_active = False
            if auto_approve > 0:
                self.date_auto_approve = datetime.now() + timedelta(minutes=auto_approve)
        super().save(*args, **kwargs)

    def do_auto_approve(self):
        # TODO: 如果后台操作需要标记为暂不审批，应该实现一个界面操作将其自动审批时间置空
        if self.date_auto_approve and datetime.now() >= self.date_auto_approve:
            self.is_active = True
            self.date_auto_approve = None
            self.save()


class Statistic(models.Model):
    # PERIOD_DAY = 'DAY'
    # PERIOD_WEEK = 'WEEK'
    # PERIOD_MONTH = 'MONTH'
    # PERIOD_CHOICES = (
    #     (PERIOD_DAY, '日'),
    #     (PERIOD_WEEK, '周'),
    #     (PERIOD_MONTH, '月'),
    # )
    #
    # period = models.CharField(
    #     verbose_name='统计周期',
    #     choices=PERIOD_CHOICES,
    # )

    date = models.DateField(
        verbose_name='统计日期',
    )

    customer_count = models.IntegerField(
        verbose_name='累计客户数量',
        default=0,
    )

    customer_count_delta = models.IntegerField(
        verbose_name='新增客户数量',
        default=0,
    )

    shop_count = models.IntegerField(
        verbose_name='累计商店数量',
        default=0,
    )

    shop_count_delta = models.IntegerField(
        verbose_name='新增商店数量',
        default=0,
    )

    goods_count = models.IntegerField(
        verbose_name='累计商品数量',
        default=0,
    )

    goods_count_delta = models.IntegerField(
        verbose_name='新增商品数量',
        default=0,
    )

    demand_count = models.IntegerField(
        verbose_name='累计需求数量',
        default=0,
    )

    demand_count_delta = models.IntegerField(
        verbose_name='新增需求数量',
        default=0,
    )

    advert_count = models.IntegerField(
        verbose_name='累计广告笔数',
        default=0,
    )

    advert_count_delta = models.IntegerField(
        verbose_name='新增广告笔数',
        default=0,
    )

    recharge_count = models.IntegerField(
        verbose_name='累计充值笔数',
        default=0,
    )

    recharge_count_delta = models.IntegerField(
        verbose_name='新增充值笔数',
        default=0,
    )

    recharge_amount = models.DecimalField(
        verbose_name='累计充值金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    recharge_amount_delta = models.DecimalField(
        verbose_name='新增充值金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    withdraw_count = models.IntegerField(
        verbose_name='累计提现笔数',
        default=0,
    )

    withdraw_count_delta = models.IntegerField(
        verbose_name='新增提现笔数',
        default=0,
    )

    withdraw_amount = models.DecimalField(
        verbose_name='累计提现金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    withdraw_amount_delta = models.DecimalField(
        verbose_name='新增提现金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    platform_income_amount = models.DecimalField(
        verbose_name='累计平台收入',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    platform_income_amount_delta = models.DecimalField(
        verbose_name='新增平台收入',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    platform_outlay_amount = models.DecimalField(
        verbose_name='累计平台支出',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    platform_outlay_amount_delta = models.DecimalField(
        verbose_name='新增平台支出',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    order_margin_amount = models.DecimalField(
        verbose_name='累计商户担保金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    order_margin_amount_delta = models.DecimalField(
        verbose_name='新增商户担保金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    advert_balance = models.DecimalField(
        verbose_name='累计广告账户余额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    advert_balance_delta = models.DecimalField(
        verbose_name='新增广告账户余额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    advert_cost = models.DecimalField(
        verbose_name='累计广告消费金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    advert_cost_delta = models.DecimalField(
        verbose_name='新增广告消费金额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    class Meta:
        verbose_name = '数据统计'
        verbose_name_plural = '数据统计'
        db_table = 'core_base_statistic'

    @staticmethod
    def make(date=None):
        """ 执行某天的统计任务
        :param date: 统计的日期（时间会被忽略）
        :return:
        """
        if type(date) == str:
            date = datetime.strptime(date, '%Y-%m-%d')
        date = date or datetime.now()
        date = datetime(day=date.day, month=date.month, year=date.year)

        # 产生记录
        stat = Statistic.objects.filter(date=date).first() or Statistic(date=date)

        # 各种类型对象基础数量统计
        from . import Customer, Shop, Goods, Demand, Advert, \
            AccountTransaction, AdvertCreditTransaction
        count_tasks = [
            (Customer, 'customer_count', 'date_created'),
            (Shop, 'shop_count', 'date_created'),
            (Goods, 'goods_count', 'date_created'),
            (Demand, 'demand_count', 'date_created'),
            (Advert, 'advert_count', 'date_created'),
        ]
        for cls, field, dt_field in count_tasks:
            # 累计
            aggr = cls.objects.filter(**dict([
                (dt_field + '__date__lte', date)
            ])).aggregate(count=models.Count('*'))
            setattr(stat, field, aggr.get('count') or 0)
            # 当日
            aggr = cls.objects.filter(**dict([
                (dt_field + '__date', date)
            ])).aggregate(count=models.Count('*'))
            setattr(stat, field + '_delta', aggr.get('count') or 0)

        # 充值数据汇总
        # TODO: 后期应该加入一些数据完整性校验以供报警使用
        aggr = AccountTransaction.objects.exclude(
            recharge_record=None,
        ).filter(
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.recharge_count = aggr.get('count') or 0
        stat.recharge_amount = aggr.get('amount') or 0

        aggr = AccountTransaction.objects.exclude(
            recharge_record=None,
        ).filter(
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.recharge_count_delta = aggr.get('count') or 0
        stat.recharge_amount_delta = aggr.get('amount') or 0

        # 提现数据汇总
        aggr = AccountTransaction.objects.exclude(
            withdraw_record=None,
        ).filter(
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.withdraw_count = aggr.get('count') or 0
        stat.withdraw_amount = aggr.get('amount') or 0

        aggr = AccountTransaction.objects.exclude(
            withdraw_record=None,
        ).filter(
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.withdraw_count_delta = aggr.get('count') or 0
        stat.withdraw_amount_delta = aggr.get('amount') or 0

        # 平台收入汇总
        aggr = AccountTransaction.objects.filter(
            user_debit=None,
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.platform_income_amount = aggr.get('amount') or 0

        aggr = AccountTransaction.objects.filter(
            user_debit=None,
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.platform_income_amount_delta = aggr.get('amount') or 0

        # 平台支出汇总
        aggr = AccountTransaction.objects.filter(
            user_credit=None,
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.platform_outlay_amount = aggr.get('amount') or 0

        aggr = AccountTransaction.objects.filter(
            user_credit=None,
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.platform_outlay_amount_delta = aggr.get('amount') or 0

        # 商户担保金额汇总
        aggr = AccountTransaction.objects.exclude(
            order=None,
        ).filter(
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        aggr2 = AccountTransaction.objects.exclude(
            order_as_receipt=None,
        ).filter(
            date_created__date__lte=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.order_margin_amount = (aggr.get('amount') or 0) - (aggr2.get('amount') or 0)

        aggr = AccountTransaction.objects.exclude(
            order=None,
        ).filter(
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        aggr2 = AccountTransaction.objects.exclude(
            order_as_receipt=None,
        ).filter(
            date_created__date=date,
        ).aggregate(count=models.Count('*'), amount=models.Sum('amount'))
        stat.order_margin_amount_delta = (aggr.get('amount') or 0) - (aggr2.get('amount') or 0)

        # 广告账户余额统计
        aggr = AdvertCreditTransaction.objects.filter(
            user_debit=None,
            date_created__date__lte=date,
        ).aggregate(amount=models.Sum('amount'))
        aggr2 = AdvertCreditTransaction.objects.filter(
            user_credit=None,
            date_created__date__lte=date,
        ).aggregate(amount=models.Sum('amount'))
        stat.advert_balance = (aggr2.get('amount') or 0) - (aggr.get('amount') or 0)
        stat.advert_cost = aggr.get('amount') or 0

        aggr = AdvertCreditTransaction.objects.filter(
            user_debit=None,
            date_created__date=date,
        ).aggregate(amount=models.Sum('amount'))
        aggr2 = AdvertCreditTransaction.objects.filter(
            user_credit=None,
            date_created__date=date,
        ).aggregate(amount=models.Sum('amount'))
        stat.advert_balance_delta = (aggr2.get('amount') or 0) - (aggr.get('amount') or 0)
        stat.advert_cost_delta = aggr.get('amount') or 0

        # 保存数据
        stat.save()
        return stat


class MessageTemplate(GeoPositionedModel,
                      AbstractMessageModel,
                      UserOwnedModel,
                      EntityModel):
    class Meta:
        verbose_name = '消息模板'
        verbose_name_plural = '消息模板'
        db_table = 'base_message_template'


class Inform(AbstractMessageModel,
             UserOwnedModel,
             EntityModel):
    """ 举报消息
    """

    STATUS_PENDING = 'PENDING'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAIL = 'FAIL'
    STATUS_CHOICES = (
        (STATUS_PENDING, '等待处理'),
        (STATUS_SUCCESS, '举报成功'),
        (STATUS_FAIL, '举报失败'),
    )

    status = models.CharField(
        verbose_name='状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    excerpt = models.CharField(
        verbose_name='摘要',
        max_length=150,
        blank=True,
        default='',
    )

    images = models.ManyToManyField(
        verbose_name='图片',
        to='ImageModel',
        related_name='%(class)ss',
        blank=True,
    )

    class Meta:
        verbose_name = '举报'
        verbose_name_plural = '举报'
        db_table = 'base_inform'


class InformableModel(models.Model):
    """ 抽象的可举报模型
    """

    informs = models.ManyToManyField(
        verbose_name='举报信息',
        to='Inform',
        related_name='%(class)ss',
        blank=True,
    )

    protect_from = models.DateTimeField(
        verbose_name='保护期限开始',
        null=True,
        blank=True,
    )

    protect_until = models.DateTimeField(
        verbose_name='保护期限结束',
        null=True,
        blank=True,
    )

    protect_pay_transactions = models.ManyToManyField(
        verbose_name='保护购买流水',
        to='AccountTransaction',
        related_name='%(class)ss_inform_protected',
        blank=True,
    )

    class Meta:
        abstract = True

    def is_protected(self):
        return self.protect_until and self.protect_from \
               and self.protect_from < datetime.now() < self.protect_until


class UserShieldModel(models.Model):
    user_shield = models.ManyToManyField(
        verbose_name='屏蔽用户',
        to=User,
        related_name='%(class)ss_shield',
        blank=True,
        help_text='这部分用户屏蔽该条信息',
    )

    class Meta:
        abstract = True


class Feedback(AbstractMessageModel,
               UserOwnedModel,
               EntityModel):
    """ 用户反馈
    """

    # STATUS_PENDING = 'PENDING'
    # STATUS_SUCCESS = 'SUCCESS'
    # STATUS_FAIL = 'FAIL'
    # STATUS_CHOICES = (
    #     (STATUS_PENDING, '等待处理'),
    #     (STATUS_SUCCESS, '举报成功'),
    #     (STATUS_FAIL, '举报失败'),
    # )

    TYPE_SUGGESTION = 'SUGGESTION'
    TYPE_COMPLAINT = 'COMPLAINT'
    TYPE_CHOICES = (
        (TYPE_SUGGESTION, '建议'),
        (TYPE_COMPLAINT, '投诉'),
    )

    type = models.CharField(
        verbose_name='反馈类型',
        choices=TYPE_CHOICES,
        max_length=20,
    )

    excerpt = models.CharField(
        verbose_name='摘要',
        max_length=150,
        blank=True,
        default='',
    )

    is_done = models.BooleanField(
        verbose_name='是否处理',
        default=False,
    )

    class Meta:
        verbose_name = '反馈'
        verbose_name_plural = '反馈'
        db_table = 'base_feedback'


class UserVotableModel(models.Model):
    """ 可投票的模型
    """
    users_vote_up = models.ManyToManyField(
        verbose_name='赞的用户',
        to=User,
        related_name='%(class)ss_voted_up',
        blank=True,
    )

    users_vote_down = models.ManyToManyField(
        verbose_name='踩的用户',
        to=User,
        related_name='%(class)ss_voted_down',
        blank=True,
    )

    class Meta:
        abstract = True

    def myvote(self):
        user = get_request().user
        if self.users_vote_up.filter(pk=user.id).exists():
            return 'up'
        elif self.users_vote_down.filter(pk=user.id).exists():
            return 'down'

    def vote(self, direction):
        assert direction in ['up', 'down'], '投票方向错误'
        user = get_request().user
        if direction == 'up':
            self.users_vote_down.remove(user)
            if self.users_vote_up.filter(pk=user.id).exists():
                self.users_vote_up.remove(user)
            else:
                self.users_vote_up.add(user)
        elif direction == 'down':
            self.users_vote_up.remove(user)
            if self.users_vote_down.filter(pk=user.id).exists():
                self.users_vote_down.remove(user)
            else:
                self.users_vote_down.add(user)

    def count_upvote(self):
        return self.users_vote_up.count()

    def count_downvote(self):
        return self.users_vote_down.count()


class UserCollectableModel(models.Model):
    """ 可收藏的模型
    """

    users_collect = models.ManyToManyField(
        verbose_name='收藏用户',
        to=User,
        related_name='%(class)ss_collected',
        blank=True,
    )

    class Meta:
        abstract = True

    def toggle_collect(self, user):
        if user.is_anonymous():
            return False
        if self.is_collected(user):
            self.users_collect.remove(user)
            return False
        self.users_collect.add(user)
        return True

    def is_collected(self, user=None):
        global_request = get_request()
        user = user or global_request and global_request.user
        if not user:
            return False
        return self.users_collect.filter(id=user.id).exists()

    def collect(self, user=None):
        global_request = get_request()
        user = user or global_request and global_request.user
        if not user:
            return False
        if not self.is_collected(user):
            self.users_collect.add(user)

    def uncollect(self, user=None):
        global_request = get_request()
        user = user or global_request and global_request.user
        if not user:
            return False
        if self.is_collected(user):
            self.users_collect.remove(user)
