from django_base.models import *
from django_finance.models import *
from django_member.models import *


@patch_methods(User)
class UserPatcher:
    def group_names(self):
        return ','.join([g.name for g in self.groups.all()]) or '-'


@patch_methods(Comment)
class CommentPatcher:
    def comment_watch_status(self):
        watch_log = self.livewatchlogs.first()
        if not watch_log:
            return None
        return watch_log.status


@patch_methods(AccountTransaction)
class AccountTransactionPatcher:
    def account_transaction_member(self):
        if self.user_debit and not self.user_credit:
            return dict(
                nickname=self.user_debit.member.nickname,
                mobile=self.user_debit.member.mobile,
            )
        elif self.user_credit and not self.user_debit:
            return dict(
                nickname=self.user_credit.member.nickname,
                mobile=self.user_credit.member.mobile,
            )
        return dict(
            nickname=None,
            mobile=None,
        )

    def account_transaction_payment_platform(self):
        if not self.type == AccountTransaction.TYPE_RECHARGE:
            return None
        return self.recharge_record.payment_record.platform

    def account_transaction_payment_out_trade_no(self):
        if not self.type == AccountTransaction.TYPE_RECHARGE:
            return None
        return self.recharge_record.payment_record.out_trade_no


# def total_recharge():
#     return AccountTransaction.objects.filter(type=AccountTransaction.TYPE_RECHARGE).aggregate(
#         amount=models.Sum('amount')).get('amount') or 0
#
#
# def total_withdraw():
#     return AccountTransaction.objects.filter(
#         type=AccountTransaction.TYPE_WITHDRAW,
#         withdraw_record__status=WithdrawRecord.STATUS_PENDING
#     ).aggregate(amount=models.Sum('amount')).get('amount') or 0


# 一般模型類


class InformableModel(models.Model):
    """ 抽象的可举报模型
    """

    informs = models.ManyToManyField(
        verbose_name='举报信息',
        to='Inform',
        related_name='%(class)ss',
        blank=True,
    )

    class Meta:
        abstract = True

    def is_protected(self):
        return self.protect_until and self.protect_from \
               and self.protect_from < datetime.now() < self.protect_until


class Member(AbstractMember,
             InformableModel,
             UserMarkableModel):
    """ 会员
    注意：用户的追踪状态通过 UserMark 的 subject=follow 类型实现
    """

    referrer = models.OneToOneField(
        verbose_name='推荐人',
        to=User,
        related_name='referrals',
        blank=True,
        null=True,
    )

    is_withdraw_blacklisted = models.BooleanField(
        verbose_name='是否已列入提现黑名单',
        default=False,
    )

    is_new_recommended = models.BooleanField(
        verbose_name='是否为首次登陆推荐名单',
        default=False,
    )

    is_follow_recommended = models.BooleanField(
        verbose_name='是否为首页追踪推荐名单',
        default=False,
    )

    tencent_sig = models.TextField(
        verbose_name='腾讯云鉴权密钥',
        blank=True,
        default='',
        help_text='腾讯云SDK产生'
    )

    tencent_sig_expire = models.DateTimeField(
        verbose_name='腾讯云鉴权密钥过期时间',
        null=True,
        blank=True,
        help_text='默认过期时间为180天'
    )

    check_member_history = models.TextField(
        verbose_name='查看谁看过我列表记录',
        null=True,
        blank=True,
        help_text='当天内查看非好友会员的id'
    )

    qrcode = models.OneToOneField(
        verbose_name='二维码',
        to=ImageModel,
        related_name='members',
        null=True,
        blank=True,
    )

    total_experience = models.IntegerField(
        verbose_name='总经验值',
        default=0,
    )

    current_level_experience = models.IntegerField(
        verbose_name='当前等级经验',
        default=0,
    )

    large_level = models.IntegerField(
        verbose_name='大等级',
        default=1,
    )

    small_level = models.IntegerField(
        verbose_name='小等级',
        default=1,
    )

    vip_level = models.IntegerField(
        verbose_name='VIP等级',
        default=0,
    )

    date_update_vip = models.DateTimeField(
        verbose_name='VIP等级更新时间',
        null=True,
        blank=True,
    )

    amount_extend = models.DecimalField(
        verbose_name='VIP续等余额',
        decimal_places=2,
        max_digits=18,
        default=0,
    )

    is_demote = models.BooleanField(
        verbose_name='是否被降级',
        default=False,
    )

    class Meta:
        verbose_name = '会员'
        verbose_name_plural = '会员'
        db_table = 'core_member'

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(user, AdminLog.TYPE_DELETE, self, '刪除會員')
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.user and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改會員')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增會員')
        if self.user:
            self.load_tencent_sig()

        # 补充资料送元气
        achievement = self.user.starmissionachievements_owned.filter(
            type=StarMissionAchievement.TYPE_INFORMATION).exists()
        if self.nickname and self.avatar and self.gender \
                and self.signature and self.birthday and self.age \
                and self.constellation and not achievement:
            self.user.starmissionachievements_owned.create(
                # todo:应该为后台可设的数值
                points=10,
                type=StarMissionAchievement.TYPE_INFORMATION,
            )
            self.user.creditstartransactions_debit.create(
                amount=10,
                remark='完成元气任务的完善资料任务奖励',
                type=CreditStarTransaction.TYPE_EARNING,
            )
        super().save(*args, **kwargs)

    def load_tencent_sig(self, force=False):
        from tencent import auth
        # 还没有超期的话忽略操作
        if not force and self.tencent_sig \
                and self.tencent_sig_expire and self.tencent_sig_expire > datetime.now():
            return
        self.tencent_sig = auth.generate_sig(
            self.user.username, settings.TENCENT_WEBIM_APPID)
        # 内部保留一定裕度，160天内不自动刷新
        self.tencent_sig_expire = datetime.now() + timedelta(days=160)

    def is_robot(self):
        """ 判斷用戶是否機器人
        :return:
        """
        return hasattr(self.user, 'robot') and self.user.robot

    def is_info_complete(self):
        """ TODO: 判断用户个人资料是否完善
        :return: 返回个人资料是否完善，用于星光任务统计
        """
        # TODO: 未實現
        raise NotImplemented()

    def is_followed_by(self, user):
        return self.is_marked_by(user, 'follow')

    def is_followed_by_current_user(self):
        """ 返回用戶是否被當前登錄用戶跟蹤
        :return:
        """
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_anonymous:
            return False
        return self.is_followed_by(user)

    def set_followed_by(self, user, is_follow=True):
        """ 設置或取消 user 對 self 的跟蹤標記
        :param user: 發起跟蹤的用戶
        :param is_follow: True 設置爲跟蹤，False 取消跟蹤
        :return:
        """
        self.set_marked_by(user, 'follow', is_follow)

    def get_follow(self):
        """ 獲取會員跟蹤（關注）的用戶列表
        :return:
        """
        return Member.get_objects_marked_by(self.user, 'follow')

    def get_followed(self):
        """ 獲取跟蹤當前會員的用戶（粉絲）列表
        :return:
        """
        return Member.objects.filter(
            user__usermarks_owned__content_type=ContentType.objects.get(
                app_label=type(self)._meta.app_label,
                model=type(self)._meta.model_name,
            ),
            user__usermarks_owned__object_id=self.pk,
            user__usermarks_owned__subject='follow',
        )

    def get_blacklist(self):
        """获取会员标记黑名单列表"""
        return Member.get_objects_marked_by(self.user, 'blacklist')

    def is_blacklist(self):
        """判斷user是否標記self爲黑名單"""
        from django_base.middleware import get_request
        user = get_request().user
        return self.is_marked_by(user, 'blacklist')

    def get_follow_count(self):
        """ 獲取跟蹤數
        :return:
        """
        return self.get_follow().count()

    def get_followed_count(self):
        """ 獲取粉絲數（被跟蹤數）
        :return:
        """
        return self.get_followed().count()

    def get_contacts(self):
        """ 獲取聯繫人列表
        :return:
        """
        return User.objects.filter(
            contacts_owned__user=self.user,
            contacts_related__author=self.user,
        ).distinct()

    def get_friend_count(self):
        """ 獲取朋友數
        :return:
        """
        return self.get_contacts().count()

    def get_live_count(self):
        return self.user.lives_owned.count()

    def get_last_live_end(self):
        """ 最后直播时间
        :return:
        """
        last_live = self.user.lives_owned.order_by('-pk').first()
        return last_live and last_live.date_end

    def get_live_total_duration(self):
        duration = 0
        lives = Live.objects.filter(author=self.user)
        for live in lives:
            duration += live.get_duration()
        return duration

    def credit_diamond(self):
        return PrizeOrder.objects.filter(
            author=self.user,
            diamond_transaction__id__gt=0,
        ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

    # def debit_diamond(self):
    #     return self.user.creditdiamondtransactions_debit.all().aggregate(
    #         amount=models.Sum('amount')).get('amount') or 0

    def debit_diamond(self):
        return PrizeOrder.objects.filter(
            diamond_transaction__user_debit=self.user,
        ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

    # def credit_star_index(self):
    #     return self.user.creditstarindextransactions_credit.all().aggregate(
    #         amount=models.Sum('amount')
    #     ).get('amount') or 0

    # def debit_star_index(self):
    #     return self.user.creditstarindexreceivertransactions_debit.all().aggregate(
    #         amount=models.Sum('amount')
    #     ).get('amount') or 0
    #     # return self.user.creditstarindextransactions_debit.all().aggregate(
    #     #     amount=models.Sum('amount')
    #     # ).get('amount') or 0

    def get_diamond_balance(self):
        # 钻石余额
        # 支出鑽石數
        credit_diamond = self.user.creditdiamondtransactions_credit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        # 收入鑽石數
        debit_diamond = self.user.creditdiamondtransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_diamond - credit_diamond

    def get_coin_balance(self):
        # 金币余额
        # 支出金币
        credit_coin = self.user.creditcointransactions_credit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        # 收入金币
        debit_coin = self.user.creditcointransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_coin - credit_coin

    def get_star_index_sender_balance(self):
        credit = self.user.creditstarindexsendertransactions_credit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        debit = self.user.creditstarindexsendertransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit - credit

    def get_star_index_receiver_balance(self):
        credit = self.user.creditstarindexreceivertransactions_credit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        debit = self.user.creditstarindexreceivertransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit - credit

    def diamond_count(self):
        """获得钻石总数
        :return:
        """
        count = self.user.creditdiamondtransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return int(count)

    # def starlight_count(self):
    #     """星光指数
    #     :return:
    #     """
    #     count = self.user.creditstarindexreceivertransactions_debit.aggregate(
    #         amount=models.Sum('amount')).get('amount') or 0
    #     return int(count)

    def get_star_balance(self):
        """星星（元气）余额
        """
        credit_star = self.user.creditstartransactions_credit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        debit_star = self.user.creditstartransactions_debit.aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_star - credit_star

    # def get_star_prize_expend(self):
    #     """元气礼物赠送的元气数量，观众背包礼物宝盒礼物使用，每500开一个礼盒
    #     """
    #
    #     transitions_amount = self.user.prizetransitions_credit.filter(
    #         prize__category__name='宝盒礼物'
    #     ).all().aggregate(
    #         amount=models.Sum('amount')).get('amount') or 0
    #     return transitions_amount - self.user.starboxrecords_owned.count() * 500

    # def get_level(self):
    #     """ 根据经验值获取用户等级
    #     :return:
    #     """
    #     import json
    #     # 获取等级规则
    #     if Option.objects.filter(key='level_rules').exists():
    #         # return 1
    #         level_rules = json.loads(Option.objects.filter(key='level_rules').first().value)
    #
    #         # 获取经验
    #         memberExp = self.experience
    #
    #         # 根据经验获取等级，等级以对象的形式传送
    #         memberLevel = {}
    #         cc = {'a': 'a'}
    #         if 'level_1' in level_rules:
    #             amount = 0  # 经验总值
    #             n = 0  # 等级
    #             for item in level_rules['level_1']:
    #                 startLevel = str(item['key']).split('_')[1]
    #                 endLevel = str(item['key']).split('_')[3]
    #                 preAmount = amount
    #                 amount += (int(endLevel) - int(startLevel) + 1) * item['value']
    #                 if memberExp < amount:
    #                     n += (memberExp - preAmount) // item['value']
    #                     memberLevel = {
    #                         'topLevel': 1,  # 图案等级
    #                         'subLevel': n,
    #                         'currentLevelExp': (memberExp - preAmount) % item['value'],  # 当前等级拥有经验
    #                         'upgradeExp': item['value'],  # 升级所需经验
    #                         'bigLevelExp': amount  # 图案等级经验总值
    #                     }
    #                     return memberLevel
    #                 n = int(endLevel)
    #             if 'level_more' in level_rules:  # 如果等级不为星星的时候
    #                 topLevel = 2  # 图案等级
    #                 for item in level_rules['level_more']:
    #                     preAmount = amount
    #                     amount += 100 * item['value']
    #                     if memberExp < amount:
    #                         subLevel = (memberExp - preAmount) // item['value'] + 1
    #                         memberLevel = {
    #                             'topLevel': topLevel,
    #                             'subLevel': subLevel,
    #                             'currentLevelExp': (memberExp - preAmount) % item['value'],  # 当前等级拥有经验
    #                             'upgradeExp': item['value'],  # 升级所需经验
    #                             'bigLevelExp': amount  # 图案等级经验总值
    #                         }
    #                         return memberLevel
    #                     topLevel += 1
    #             else:
    #                 raise ValueError('level_rules 没有定义好 ： \'level_more\'')
    #         else:
    #             raise ValueError('level_rules 没有定义好 ： \'level_1\'')
    #
    #     # TODO: 未实现
    #     return 1

    def get_level(self):
        """
        獲得用戶等級
        :return:
        """
        level_rules = json.loads(Option.get('level_rules') or '[]')
        if not level_rules:
            return 1

        return 1

    def get_vip_level(self):
        """ 获取用户 VIP 等级
        :return:
        """
        return self.vip_level

    def update_vip_level(self, recharge_record):
        """
        每次储值后，计算新的vip等级
        :return:
        """
        if not Option.get('vip_rules'):
            return 0
        vip_rules = json.loads(Option.get('vip_rules'))
        current_vip_level = self.vip_level
        # 最近一个月的储值量
        amount_this_month = RechargeRecord.objects.filter(
            author=recharge_record.author,
            date_created__lte=recharge_record.date_created,
            date_created__gt=recharge_record.date_created - timedelta(days=30),
        ).aggregate(amount=models.Sum('amount')).get('amount') or 0
        # 当前vip为0，而且最近一个月储值低于vip1的储值要求，直接返回
        if current_vip_level == 0 and amount_this_month < vip_rules[0].get('recharge'):
            return
        for i in range(current_vip_level, len(vip_rules)):
            if 1 <= current_vip_level == i:
                if vip_rules[i].get('recharge') <= amount_this_month < vip_rules[i + 1].get('recharge'):
                    # 升级vip
                    self.upgrade(i + 1, recharge_record.date_created, amount_this_month - vip_rules[i].get('recharge'))
                    break
                elif amount_this_month < vip_rules[i].get('recharge') and recharge_record.amount + self.amount_extend >= \
                        vip_rules[i - 1].get('recharge_next_month'):
                    # 续等vip
                    self.upgrade(i, 0, 0)
                    break
                elif amount_this_month < vip_rules[i].get('recharge') and recharge_record.amount + self.amount_extend < \
                        vip_rules[i - 1].get('recharge_next_month'):
                    # 不够续等vip，把钱存在续等余额
                    self.upgrade(i, None, recharge_record.amount)
                    break
            if i == len(vip_rules) - 1:
                if amount_this_month >= vip_rules[i].get('recharge'):
                    # 升级vip
                    self.upgrade(i + 1, recharge_record.date_created, amount_this_month - vip_rules[i].get('recharge'))
                    break
                elif amount_this_month < vip_rules[i].get('recharge') and recharge_record.amount + self.amount_extend >= \
                        vip_rules[i - 1].get('recharge_next_month'):
                    # 续等vip
                    self.upgrade(i, 0, 0)
                    break
                elif amount_this_month < vip_rules[i].get('recharge') and recharge_record.amount + self.amount_extend < \
                        vip_rules[i - 1].get('recharge_next_month'):
                    # 不够续等vip,把钱存在续等余额
                    self.upgrade(i, None, recharge_record.amount)
                    break
            elif i < len(vip_rules) - 1:
                if vip_rules[i].get('recharge') <= amount_this_month < vip_rules[i + 1].get('recharge'):
                    self.upgrade(i + 1, recharge_record.date_created, amount_this_month - vip_rules[i].get('recharge'))
                    break

    def upgrade(self, level, date_update_vip, amount_extend):
        """
        执行更新vip等级,把多出的充值额放在 amount_extend
        :param level:
        :param date_update_vip:
        :return:
        """
        self.vip_level = level
        if date_update_vip:
            self.date_update_vip = date_update_vip
            self.make_update_vip_plan(date_update_vip + timedelta(days=30 * level), self.id)
        elif date_update_vip == 0:
            self.make_update_vip_plan(None, self.id)
        if amount_extend:
            self.amount_extend += amount_extend
        else:
            self.amount_extend = 0
        self.save()

    @staticmethod
    def make_update_vip_plan(date_planned, member_id):
        planned_task = PlannedTask.objects.filter(
            method='change_vip_level',
            args__exact=json.dumps([member_id]),
        ).first()
        if not planned_task:
            PlannedTask.make('change_vip_level', date_planned, json.dumps([member_id]))
            return
        if not date_planned:
            planned_task.date_planned += timedelta(days=30)
        else:
            planned_task.date_planned = date_planned
        planned_task.save()

    def get_today_watch_mission_count(self):
        """当前用户当天完成观看任务次数
        """
        return StarMissionAchievement.objects.filter(
            author=self.user,
            date_created__date=datetime.now().date(),
            type=StarMissionAchievement.TYPE_WATCH,
        ).count()

    #
    # def get_information_mission_count(self):
    #     """当前用户完善资料任务完成数
    #     """
    #
    #     return StarMissionAchievement.objects.filter(
    #         author=self.user,
    #         type=StarMissionAchievement.TYPE_INFORMATION).count()

    def is_living(self):
        # 是否在直播
        live = self.user.lives_owned.filter().order_by('-date_created')
        if live.exists():
            if live.first().date_end:
                return False
            else:
                return live.first().id
        else:
            return False

    def contact_form_me(self):
        # 我的联系人
        me = get_request().user
        return Contact.objects.filter(
            author=me,
            user=self.user,
        ).exists()

    def contact_to_me(self):
        # 对方的联系人有我
        me = get_request().user
        return Contact.objects.filter(
            author=self.user,
            user=me,
        ).exists()

    def add_withdraw_blacklisted(self):
        """
        添加到提现黑名单（顺手驳回该用户其他申请中的提现）
        :return:
        """
        self.is_withdraw_blacklisted = True
        self.save()
        # 把剩下仍在申请中的提现全部驳回
        for withdraw_record in WithdrawRecord.objects.filter(author=self.user, status=WithdrawRecord.STATUS_PENDING):
            withdraw_record.reject()

    def get_first_live_date(self):
        """用戶第一次直播的時間"""

        if self.user.lives_owned.exists():
            return self.user.lives_owned.order_by('-date_created').first().date_created
        else:
            return False

    def add_diamond_badge(self):
        """
        增加主播收到鑽石徽章.
        在觀衆送禮物時觸發
        """
        badges = Badge.objects.filter(
            date_from__lt=datetime.now(),
            date_to__gt=datetime.now(),
            badge_item=Badge.ITEM_COUNT_RECEIVE_DIAMOND,
            item_value__lt=self.diamond_count()
        ).exclude(
            records__author=self.user
        ).all()
        for badge in badges:
            BadgeRecord.objects.create(
                author=self.user,
                badge=badge,
            )

    def is_checkin_daily(self):
        """
        今天是否已经签到
        """
        return self.user.dailycheckinlogs_owned.filter(
            date_created__date=datetime.now().date()
        ).exists()

    def set_blacklist_by(self, user, is_black=True):
        """ 設置user的黑名單增加self
        :param user: 黑名單作者
        :param is_black: True 設置到黑名單，False 取消黑名單
        :return:
        """
        self.set_marked_by(user, 'blacklist', is_black)

    def is_not_disturb(self):
        """me是否設置self爲免打擾
        要有好友关系并且在关系设置is_not_disturb为True"""
        me = get_request().user
        contact = Contact.objects.filter(author=me, user=self.user)
        if contact.exists():
            setting = contact.first().settings.filter(key='is_not_disturb')
            if setting.exists() and setting.first().value == '1':
                return True
        return False

    def update_search_history(self, key):
        """
        更新搜索历史
        :param key:
        :return:
        """
        search_history = self.search_history.split(',')
        if key in search_history:
            search_history.remove(key)
        search_history.insert(0, key)
        string = ','.join(search_history)
        self.search_history = string
        self.save()

    def update_check_member_history(self, member):
        """
        更新我查看 ‘看过我的人’列表中非好友会员记录，
        如果为会员可以无限查看，
        如果不是会员，只能看非好友关系的人一天十个
        """
        contact_form_me = Contact.objects.filter(
            author=self.user,
            user=member.user,
        ).exists()
        contact_to_me = Contact.objects.filter(
            author=member.user,
            user=self.user,
        ).exists()
        if contact_form_me and contact_to_me:
            return member
        check_history = self.check_member_history.split(',')
        if len(check_history) >= 10 and not str(member.user.id) in check_history \
                and self.get_vip_level() < 5 and self.get_level() < 5:
            # 查看已经超过10个并且没有会员等级
            return False
        if str(member.user.id) in check_history:
            check_history.remove(str(member.user.id))
        check_history.insert(0, str(member.user.id))
        string = ','.join(check_history)
        self.check_member_history = string
        self.save()
        return member

    def member_activity_award(self, activity, awards, status='COMPLETE'):
        """
        用户 获得的活动奖励
        @:param  activity 活动对象
                 awards {'value': 10, 'type': 'coin'}
                        type: '', // experience:经验值/icoin:i币/coin:金币/star:星星/prize:礼物/contribution:贡献值/badge:勋章
                 status 活动完成状态
        """
        coin_transaction = None
        diamond_transaction = None
        prize_transaction = None
        star_transaction = None
        badge_record = None
        exp_transaction = None
        if awards['type'] == 'coin':
            # 金币
            coin_transaction = CreditCoinTransaction.objects.create(
                user_debit=self.user,
                type=CreditCoinTransaction.TYPE_ACTIVITY,
                amount=awards['value'],
            )
        if awards['type'] == 'diamond':
            # 钻石
            diamond_transaction = CreditDiamondTransaction.objects.create(
                user_debit=self.user,
                type=CreditDiamondTransaction.TYPE_ACTIVITY,
                amount=awards['value'],
            )
        if awards['type'] == 'prize':
            # 礼物
            prize_transaction = PrizeTransaction.objects.create(
                user_debit=self.user,
                amount=1,
                type=PrizeTransaction.TYPE_ACTIVITY_GAIN,
                prize=Prize.objects.get(pk=awards['value']),
                source_tag=PrizeTransaction.SOURCE_TAG_ACTIVITY,
            )
        if awards['type'] == 'experience':
            # 经验
            # self.experience += awards['value']
            exp_transaction = ExperienceTransaction.make(self.user, awards['value'],
                                                         ExperienceTransaction.TYPE_ACTIVITY)
            exp_transaction.update_level()
            # self.save()
        if awards['type'] == 'star':
            # 元气
            star_transaction = CreditStarTransaction(
                user_debit=self.user,
                amount=awards['value'],
                type=CreditStarTransaction.TYPE_ACTIVITY,
            )
        if awards['type'] == 'badge':
            # 徽章
            badge_record = BadgeRecord.objects.create(
                author=self.user,
                badge=Badge.objects.get(pk=awards['value'])
            )
        # todo  i币 贡献值
        ActivityParticipation.objects.create(
            author=self.user,
            activity=activity,
            status=status,
            coin_transaction=coin_transaction,
            diamond_transaction=diamond_transaction,
            prize_transaction=prize_transaction,
            star_transaction=star_transaction,
            badge_record=badge_record,
            experience_transaction=exp_transaction,
        )


class LoginRecord(UserOwnedModel):
    """
    登录记录
    """
    date_login = models.DateTimeField(
        verbose_name='登录时间',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = '登录记录'
        verbose_name_plural = '登录记录'
        db_table = 'core_login_record'

    @staticmethod
    def make(author):
        return LoginRecord.objects.create(author=author)


class ExperienceTransaction(EntityModel, UserOwnedModel):
    """
    经验流水
    """
    experience = models.IntegerField(
        verbose_name='经验值',
    )

    TYPE_SIGN = 'SIGN'
    TYPE_SHARE = 'SHARE'
    TYPE_RECEIVE = 'RECEIVE'
    TYPE_SEND = 'SEND'
    TYPE_WATCH = 'WATCH'
    TYPE_LIVE = 'LIVE'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_OTHER = 'OTHER'
    TYPE_CHOICES = (
        (TYPE_SIGN, '登录'),
        (TYPE_SHARE, '分享'),
        (TYPE_RECEIVE, '收礼'),
        (TYPE_SEND, '送礼'),
        (TYPE_WATCH, '观看直播'),
        (TYPE_LIVE, '直播'),
        (TYPE_LIVE, '活动'),
        (TYPE_OTHER, '其他'),
    )

    type = models.CharField(
        verbose_name='类型',
        max_length=10,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '经验流水'
        verbose_name_plural = '经验流水'
        db_table = 'core_experience_transaction'

    @staticmethod
    def make(author, experience, transaction_type):
        experience_transaction = ExperienceTransaction.objects.create(
            author=author,
            experience=experience,
            type=transaction_type,
        )
        return experience_transaction

    def update_level(self):
        """
        根据当前经验流水，更新用户等级
        :return:
        """
        member = self.author.member
        large_level = member.large_level
        small_level = member.small_level
        current_level_exp = member.current_level_experience
        total_exp = member.total_experience
        total_exp += self.experience
        if not Option.get('level_rules'):
            return
        rules = json.loads(Option.get('level_rules'))
        if large_level == 1 and small_level <= 20:
            demand = rules.get('level_1')[0].get('value')
            if current_level_exp + self.experience >= demand:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        elif large_level == 2 and 20 < small_level <= 40:
            demand = rules.get('level_1')[1].get('value')
            if current_level_exp + self.experience >= demand:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        elif large_level == 1 and 40 < small_level <= 60:
            demand = rules.get('level_1')[2].get('value')
            if current_level_exp + self.experience >= demand:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        elif large_level == 1 and 60 < small_level <= 80:
            demand = rules.get('level_1')[3].get('value')
            if current_level_exp + self.experience >= demand:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        elif large_level == 1 and 80 < small_level <= 99:
            demand = rules.get('level_1')[4].get('value')
            if current_level_exp + self.experience >= demand and small_level == 99:
                current_level_exp = current_level_exp + self.experience - demand
                small_level = 1
                large_level = 2
            elif current_level_exp + self.experience >= demand and small_level < 99:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        elif large_level > 1:
            demand = rules.get('level_more')[large_level - 2].get('value')
            if current_level_exp + self.experience >= demand and small_level == 99:
                current_level_exp = current_level_exp + self.experience - demand
                small_level = 1
                large_level += 1
            elif current_level_exp + self.experience >= demand and small_level < 99:
                current_level_exp = current_level_exp + self.experience - demand
                small_level += 1
            else:
                current_level_exp += self.experience
        member.small_level = small_level
        member.large_level = large_level
        member.total_experience = total_exp
        member.current_level_experience = current_level_exp
        member.save()


class Robot(models.Model):
    """ 机器人
    创建一个机器人会强制需要对应一个用户，这个用户对应一个 Member
    通过修改 Robot 模型的信息会影响该虚拟会员在系统中的显示
    默认情况下机器人不显示在外部用户列表中
    """
    user = models.OneToOneField(
        verbose_name='用户',
        to=User,
        related_name='robot',
        primary_key=True,
    )

    count_friend = models.IntegerField(
        verbose_name='好友数',
        default=0,
    )

    count_follow = models.IntegerField(
        verbose_name='追踪数',
        default=0,
    )

    count_live = models.IntegerField(
        verbose_name='发起直播数',
        default=0,
    )

    count_diamond = models.IntegerField(
        verbose_name='钻石数',
        default=0,
    )

    count_prize_sent = models.IntegerField(
        verbose_name='送出礼物数',
        default=0,
    )

    class Meta:
        verbose_name = '机器人'
        verbose_name_plural = '机器人'
        db_table = 'core_robot'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改機器人')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增機器人')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(user, AdminLog.TYPE_DELETE, self, '刪除機器人')
        super().delete(*args, **kwargs)


class CelebrityCategory(EntityModel):
    TYPE_LIVE = 'LIVE'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_CHOICES = (
        (TYPE_LIVE, '直播'),
        (TYPE_ACTIVITY, '活動'),
    )

    type = models.CharField(
        verbose_name='分類類別',
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
        null=True,
    )

    live_category = models.ForeignKey(
        verbose_name='直播分類',
        to='LiveCategory',
        related_name='celebrity_categories',
        null=True,
        blank=True,
    )

    activity = models.ForeignKey(
        verbose_name='活動',
        to='Activity',
        related_name='celebrity_categories',
        null=True,
        blank=True,
    )

    leader = models.ForeignKey(
        verbose_name='当前获得者',
        to=User,
        related_name='celebrity_categories',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '众星云集分类'
        verbose_name_plural = '众星云集分类'
        db_table = 'core_celebrity_category'

    def get_category(self):
        if self.type == self.TYPE_LIVE and self.live_category:
            return dict(
                category_id=self.live_category.id,
                category_name=self.live_category.name,
            )
        elif self.type == self.TYPE_ACTIVITY and self.activity:
            return dict(
                category_id=self.activity.id,
                category_name=self.activity.name,
            )
        return dict(category_id=None, category_name=None)


class CreditStarTransaction(AbstractTransactionModel):
    """ 元气流水
    每日签到或者元气任务可以获得元气，元气可用于购买赠送元气礼品
    """
    TYPE_LIVE_GIFT = 'LIVE_GIFT'
    TYPE_EARNING = 'EARNING'
    TYPE_ADMIN = 'ADMIN'
    TYPE_DAILY = 'DAILY'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_CHOICES = (
        (TYPE_LIVE_GIFT, '直播赠送'),
        (TYPE_EARNING, '任務獲得'),
        (TYPE_ADMIN, '後臺補償'),
        (TYPE_DAILY, '签到获得'),
        (TYPE_ACTIVITY, '活动获得'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '星星（元气）流水'
        verbose_name_plural = '星星（元气）流水'
        db_table = 'core_credit_star_transaction'


class CreditStarIndexReceiverTransaction(AbstractTransactionModel):
    """ 元气指数（收礼产生类）
    主播用户收到元气礼品时可以获得此类指数，每达到 500 个就可以换一个元气宝盒
    """
    TYPE_GENERATE = 'GENERATE'
    TYPE_BOX_EXPENSE = 'BOX_EXPENSE'
    TYPE_CHOICES = (
        (TYPE_GENERATE, '送禮產生'),
        (TYPE_BOX_EXPENSE, '寶盒消耗'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '星光指数（元氣）流水（收礼）'
        verbose_name_plural = '星光指数（元氣）流水（收礼）'
        db_table = 'core_credit_star_index_receiver_transaction'


class CreditStarIndexSenderTransaction(AbstractTransactionModel):
    """ 元气指数（送礼产生类）
    用户送出元气礼品时可以获得此类指数，每达到 500 个就可以换一个元气宝盒
    """

    TYPE_GENERATE = 'GENERATE'
    TYPE_BOX_EXPENSE = 'BOX_EXPENSE'
    TYPE_CHOICES = (
        (TYPE_GENERATE, '送禮產生'),
        (TYPE_BOX_EXPENSE, '寶盒消耗'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '星光指数（元氣）流水（送礼）'
        verbose_name_plural = '星光指数（元氣）流水（送礼）'
        db_table = 'core_credit_star_index_sender_transaction'


class CreditDiamondTransaction(AbstractTransactionModel):
    TYPE_ADMIN = 'ADMIN'
    TYPE_LIVE_GIFT = 'LIVE_GIFT'
    TYPE_EXCHANGE = 'EXCHANGE'
    TYPE_WITHDRAW = 'WITHDRAW'
    TYPE_ACTIVITY_EXPENSE = 'ACTIVITY_EXPENSE'
    TYPE_BOX = 'BOX'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_CHOICES = (
        (TYPE_ADMIN, '管理員發放'),
        (TYPE_LIVE_GIFT, '直播赠送'),
        (TYPE_EXCHANGE, '兌換'),
        (TYPE_WITHDRAW, '提現'),
        (TYPE_ACTIVITY_EXPENSE, '活動消費'),
        (TYPE_BOX, '开启元气宝盒'),
        (TYPE_ACTIVITY, '活动'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '钻石流水'
        verbose_name_plural = '钻石流水'
        db_table = 'core_credit_diamond_transaction'


class CreditCoinTransaction(AbstractTransactionModel):
    TYPE_ADMIN = 'ADMIN'
    TYPE_LIVE_GIFT = 'LIVE_GIFT'
    TYPE_RECHARGE = 'RECHARGE'
    TYPE_EXCHANGE = 'EXCHANGE'
    TYPE_BOX = 'BOX'
    TYPE_BARRAGE = 'BARRAGE'
    TYPE_FAMILY_MODIFY = 'FAMILY_MODIFY'
    TYPE_DAILY = 'DAILY'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_CHOICES = (
        (TYPE_ADMIN, '管理員發放'),
        (TYPE_LIVE_GIFT, '直播赠送'),
        (TYPE_RECHARGE, '充值'),
        (TYPE_EXCHANGE, '兌換'),
        (TYPE_BOX, '打開元氣寶盒'),
        (TYPE_BARRAGE, '發送彈幕消費'),
        (TYPE_FAMILY_MODIFY, '家族長修改頭銜'),
        (TYPE_DAILY, '每日签到获得'),
        (TYPE_ACTIVITY, '活动'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    class Meta:
        verbose_name = '金币流水'
        verbose_name_plural = '金币流水'
        db_table = 'core_credit_coin_transaction'

    @staticmethod
    def get_coin_by_product_id(product_id):
        """
        通过coin_recharge_rules配置获取对应金币数
        [{"product": "", "coin": int, "money": int, "award": int, "award2": int}]
        :return:
        """
        rules = json.loads(Option.get('coin_recharge_rules') or '[]')
        for rule in rules:
            if rule.get('product') == product_id:
                return rule.get('coin')
        return None

    @staticmethod
    def get_award_coin_by_product_id(product_id, is_first=False):
        """
        通过coin_recharge_rules配置获取对应金币数
        [{"product": "", "coin": int, "money": int, "award": int, "award2": int}]
        :param product_id:
        :return:
        """
        rules = json.loads(Option.get('coin_recharge_rules') or '[]')
        for rule in rules:
            if rule.get('product') == product_id:
                if is_first:
                    return rule.get('award')
                return rule.get('award2')
        return None


class BadgeRecord(UserOwnedModel):
    badge = models.ForeignKey(
        verbose_name='徽章',
        to='Badge',
        related_name='records',
    )

    date_created = models.DateTimeField(
        verbose_name='獲得時間',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = '徽章記錄'
        verbose_name_plural = '徽章記錄'
        db_table = 'core_badge_record'
        unique_together = (('author', 'badge'),)


class Badge(EntityModel):
    """ 徽章
    """
    icon = models.OneToOneField(
        verbose_name='图标',
        to=ImageModel,
        related_name='badge',
        null=True,
        blank=True,
    )

    validity = models.IntegerField(
        verbose_name='有效期天数',
        default=0,
    )

    date_from = models.DateTimeField(
        verbose_name='起始可用时间',
        null=True,
        blank=True,
    )

    date_to = models.DateTimeField(
        verbose_name='结束可用时间',
        null=True,
        blank=True,
    )

    # item_key = models.CharField(
    #     verbose_name='元件序号',
    #     max_length=20,
    #     blank=True,
    #     default='根据后台指定的几种任务元件的编号',
    # )
    ITEM_SEND_PRIZE = 'SEND_PRIZE'
    ITEM_WATCH_LIVE_DURATION = 'WATCH_LIVE_DURATION'
    ITEM_COUNT_WATCH_LOG = 'COUNT_WATCH_LOG'
    ITEM_COUNT_FOLLOWED = 'COUNT_FOLLOWED'
    ITEM_COUNT_FRIEND = 'COUNT_FRIEND'
    ITEM_COUNT_LOGIN = 'COUNT_LOGIN'
    ITEM_COUNT_INVITE = 'COUNT_INVITE'
    ITEM_COUNT_ENTER_LIVE = 'COUNT_ENTER_LIVE'
    ITEM_COUNT_SHARE_LIVE = 'COUNT_SHARE_LIVE'
    ITEM_COUNT_LIVE = 'COUNT_LIVE'
    ITEM_COUNT_RECEIVE_DIAMOND = 'COUNT_RECEIVE_DIAMOND'
    ITEM_COUNT_RECEIVE_PRIZE = 'COUNT_RECEIVE_PRIZE'
    ITEM_BINDING_MOBILE = 'BINDING_MOBILE'
    ITEM_INFO_COMPLETE = 'INFO_COMPLETE'
    ITEM_LIVE_DURATION = 'LIVE_DURATION'
    ITEM_CONTRIBUTION = 'CONTRIBUTION'
    ITEM_SPECIAL = 'SPECIAL'
    ITEM_CHOICES = (
        (ITEM_SEND_PRIZE, '送礼物额度'),
        (ITEM_WATCH_LIVE_DURATION, '观看时长'),
        (ITEM_COUNT_WATCH_LOG, '累计观看数'),
        (ITEM_COUNT_FOLLOWED, '追踪数'),
        (ITEM_COUNT_FRIEND, '好友数'),
        (ITEM_COUNT_LOGIN, '连续登录天数'),
        (ITEM_COUNT_INVITE, '邀请好友注册数'),
        (ITEM_COUNT_ENTER_LIVE, '直播间访谈数'),
        (ITEM_COUNT_SHARE_LIVE, '分享直播间数'),
        (ITEM_COUNT_LIVE, '连续开播的天数'),
        (ITEM_COUNT_RECEIVE_DIAMOND, '收到钻石额度'),
        (ITEM_COUNT_RECEIVE_PRIZE, '收到礼物数量'),
        (ITEM_BINDING_MOBILE, '绑定手机'),
        (ITEM_INFO_COMPLETE, '完善个人资料'),
        (ITEM_LIVE_DURATION, '开播时数'),
        (ITEM_CONTRIBUTION, '贡献值（家族任务限定）'),
        (ITEM_SPECIAL, '特殊'),
    )

    badge_item = models.CharField(
        verbose_name='任务元件',
        max_length=50,
        default=ITEM_SEND_PRIZE,
        choices=ITEM_CHOICES,
    )

    item_value = models.IntegerField(
        verbose_name='元件数值',
        blank=True,
        default=0,
        help_text='指定条件达到所需的数值'
    )

    class Meta:
        verbose_name = '徽章'
        verbose_name_plural = '徽章'
        db_table = 'core_badge'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改徽章')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增徽章')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(user, AdminLog.TYPE_DELETE, self, '刪除徽章')
        super().delete(*args, **kwargs)


class DailyCheckInLog(UserOwnedModel):
    date_created = models.DateTimeField(
        verbose_name='签到时间',
        auto_now_add=True,
    )

    prize_coin_transaction = models.OneToOneField(
        verbose_name='奖励金币流水记录',
        to='CreditCoinTransaction',
        null=True,
        blank=True,
    )

    prize_star_transaction = models.OneToOneField(
        verbose_name='奖励星星流水记录',
        to='CreditStarTransaction',
        null=True,
        blank=True,
    )

    coin_transaction = models.OneToOneField(
        verbose_name='奖励金币记录',
        to='CreditCoinTransaction',
        related_name='daily_check_in_log',
        null=True,
        blank=True,
    )

    is_continue = models.BooleanField(
        verbose_name='连签奖励',
        default=False,
    )

    sign_experience_transaction = models.ForeignKey(
        verbose_name='签到经验流水',
        to='ExperienceTransaction',
        related_name='daily_check_in_log',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '每日签到'
        verbose_name_plural = '每日签到'
        db_table = 'core_daily_check_in_log'

    @staticmethod
    def check_in(user):
        """ TODO: 实现签到
        :param user:
        :return:
        """

        daily_option = json.loads(Option.get('daily_sign_award'))
        # 每日签到奖励
        award_list = daily_option['daily_seven_days']
        # 连签配置
        continue_award = daily_option['daily_for_days']
        # 今天簽到獎勵
        today_daily_award = award_list[datetime.now().weekday()]
        daily_check = None
        continue_daily_check = None
        coin_transaction = None
        star_transaction = None
        sign_exp_transaction = None

        if today_daily_award['type'] == 'star':
            star_transaction = CreditStarTransaction.objects.create(
                user_debit=user,
                amount=today_daily_award['value'],
                remark='每日签到获得',
                type=CreditStarTransaction.TYPE_DAILY,
            )
        elif today_daily_award['type'] == 'coin':
            coin_transaction = CreditCoinTransaction.objects.create(
                user_debit=user,
                amount=today_daily_award['value'],
                remark='每日签到获得',
                type=CreditCoinTransaction.TYPE_DAILY,
            )
        sign_exp_transaction = ExperienceTransaction.make(user, int(Option.get('experience_points_login') or 5),
                                                          ExperienceTransaction.TYPE_SIGN)
        sign_exp_transaction.update_level()
        daily_check = DailyCheckInLog.objects.create(
            author=user,
            prize_star_transaction=star_transaction,
            coin_transaction=coin_transaction,
        )

        # 连签要求天数
        continue_check = DailyCheckInLog.objects.filter(
            author=user,
            is_continue=True,
        ).order_by('-date_created')
        last_continue_check_date = None
        if continue_check.exists():
            last_continue_check_date = continue_check.first().date_created
        else:
            last_continue_check_date = DailyCheckInLog.objects.filter(
                author=user,
            ).order_by('date_created').first().date_created

        continue_days = continue_award['days']
        continue_success = True
        while continue_days > 0:
            continue_days -= 1
            daily = DailyCheckInLog.objects.filter(
                author=user,
                date_created__date=(datetime.now() - timedelta(days=continue_days)).date(),
                date_created__date__gt=last_continue_check_date.date(),
            ).exists()
            if not daily:
                continue_success = False
        # 连签奖励
        if continue_success:
            continue_coin_transaction = None
            continue_star_transaction = None
            if continue_award['type'] == 'star':
                continue_star_transaction = CreditStarTransaction.objects.create(
                    user_debit=user,
                    amount=continue_award['value'],
                    remark='连续签到获得',
                    type=CreditStarTransaction.TYPE_DAILY,
                )
            elif continue_award['type'] == 'coin':
                continue_coin_transaction = CreditCoinTransaction.objects.create(
                    user_debit=user,
                    amount=continue_award['value'],
                    remark='连续签到获得',
                    type=CreditCoinTransaction.TYPE_DAILY,
                )
            continue_daily_check = DailyCheckInLog.objects.create(
                author=user,
                prize_star_transaction=continue_star_transaction,
                coin_transaction=continue_coin_transaction,
                is_continue=True,
            )

        return dict(
            daily_check=daily_check,
            continue_daily_check=continue_daily_check,
        )


class Family(UserOwnedModel,
             EntityModel):
    logo = models.OneToOneField(
        verbose_name='图标',
        to=ImageModel,
        related_name='family',
        null=True,
        blank=True,
    )

    qrcode = models.OneToOneField(
        verbose_name='二维码',
        to=ImageModel,
        related_name='familys',
        null=True,
        blank=True,
    )

    users = models.ManyToManyField(
        verbose_name='家族成员',
        to=User,
        through='FamilyMember',
        # through_fields=('family', 'author'),
        related_name='families',
    )

    messages = models.ManyToManyField(
        verbose_name='家族消息',
        to=Message,
        related_name='families',
        blank=True,
    )

    mission_unlock_duration = models.IntegerField(
        verbose_name='发布任务时间间隔',
        default=0,
        help_text='后台设置的家族发布任务时间间隔（秒），'
                  '发布了任务之后距离下个任务之间需要间隔这个时间',
    )

    mission_element_settings = models.TextField(
        verbose_name='任务元件设置',
        blank=True,
        default='',
        help_text='JSON字段，后台设定设定各类任务元件的开关以及数量，'
                  '逻辑需要额外定义，前端做对应的实现',
    )

    award_element_settings = models.TextField(
        verbose_name='奖励元件设置',
        blank=True,
        default='',
        help_text='JSON字段，后台设定设定各类奖励元件的开关以及数量，'
                  '逻辑需要额外定义，前端做对应的实现',
    )

    level_settings = models.TextField(
        verbose_name='家族等级设定',
        blank=True,
        default='',
        help_text='JSON字段，后台设定设定家族等级规则，包括等级分段、所需贡献值以及颜色'
                  '逻辑需要额外定义，前端做对应的实现',
    )

    date_mission_unlock = models.DateTimeField(
        verbose_name='发布任务解锁日期',
        default=datetime(1900, 1, 1)
    )

    family_introduce = models.TextField(
        verbose_name='家族简介',
        null=True,
        blank=True,
        default='',
    )

    is_verify = models.BooleanField(
        verbose_name='是否需要验证',
        default=True,
    )

    class Meta:
        verbose_name = '家族'
        verbose_name_plural = '家族'
        db_table = 'core_family'

    def contribution_points(self):
        """ TODO: 返回家族贡献值，通过会员的记录，后期考虑是否缓存
        :return:
        """
        raise NotImplemented()

    def level(self):
        """ TODO: 计算家族等级
        :return:
        """
        raise NotImplemented()

    def get_count_admin(self):
        """
        审批通过的家族管理员数
        :return:
        """
        return self.users.filter(
            familymembers_owned__status=FamilyMember.STATUS_APPROVED,
            familymembers_owned__role=FamilyMember.ROLE_ADMIN,
        ).count()

    def get_count_family_member(self):
        """
        审核通过的家族成员数
        :return:
        """
        return self.users.filter(
            familymembers_owned__status=FamilyMember.STATUS_APPROVED,
        ).count()

    def get_count_family_article(self):
        """
        家族公告数
        :return:
        """
        return FamilyArticle.objects.filter(family=self).count()

    def get_count_family_mission(self):
        """
        家族任务数
        :return:
        """
        return FamilyMission.objects.filter(family=self).count()

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改家族{}'.format(self.name))
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新建家族{}'.format(self.name))
        else:
            super().save(*args, **kwargs)

        # WebIM 建群
        from tencent.webim import WebIM
        webim = WebIM(settings.TENCENT_WEBIM_APPID)
        create = webim.create_group(
            self.author.username,
            'Family_{}'.format(self.id),
            type=WebIM.GROUP_TYPE_PRIVATE,
            group_id='family_{}'.format(self.id),
        )

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除家族{}'.format(self.name),
            )
        super().delete(*args, **kwargs)

    def get_family_mission_cd(self):
        """
        家族任务冷却时间，返回秒
        """
        last_mission = self.missions.filter(
        ).order_by('-date_created')

        if last_mission.exists():
            last_mission_created = last_mission.first().date_created
            option = json.loads(Option.get('family_mission_cd'))
            next_mission_created = last_mission_created + timedelta(days=option['days']) + timedelta(
                hours=option['hours']) + timedelta(
                minutes=option['minutes'])

            if next_mission_created < datetime.now():
                return 0
            else:
                return (next_mission_created - datetime.now()).seconds + \
                       (next_mission_created - datetime.now()).days * 24 * 60 * 60
        else:
            return 0


class FamilyMember(UserOwnedModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='members',
    )

    title = models.CharField(
        verbose_name='称号',
        max_length=100,
        null=True,
        blank=True,
    )

    join_message = models.CharField(
        verbose_name='加入信息',
        max_length=255,
        help_text='用户在申请加入家族的时候填写的信息',
        null=True,
        blank=True,
    )

    STATUS_PENDING = 'PENDING'
    STATUS_REJECTED = 'REJECTED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_BLACKLISTED = 'BLACKLISTED'
    STATUS_CHOICES = (
        (STATUS_PENDING, '等待审批'),
        (STATUS_REJECTED, '被拒绝'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_BLACKLISTED, '黑名单'),
    )

    status = models.CharField(
        verbose_name='是否审批通过',
        max_length=20,
        choices=STATUS_CHOICES,
    )

    date_approved = models.DateTimeField(
        verbose_name='审批通过时间',
        null=True,
        blank=True,
    )

    ROLE_MASTER = 'MASTER'
    ROLE_ADMIN = 'ADMIN'
    ROLE_NORMAL = 'NORMAL'
    ROLE_CHOICES = (
        (ROLE_MASTER, '族长'),
        (ROLE_ADMIN, '管理员'),
        (ROLE_NORMAL, '平民'),
    )

    role = models.CharField(
        verbose_name='角色',
        max_length=20,
        default=ROLE_NORMAL,
        choices=ROLE_CHOICES,
    )

    is_ban = models.BooleanField(
        verbose_name='是否禁言',
        default=False,
    )

    class Meta:
        verbose_name = '家族成员'
        verbose_name_plural = '家族成员'
        db_table = 'core_family_member'

    def __str__(self):
        return '{} - {} - {}'.format(self.family.name, self.get_role_display(), self.author.member.mobile)

    def save(self, *args, **kwargs):
        """
        自动将人加入到群组中
        :param args:
        :param kwargs:
        :return:
        """
        super().save(*args, **kwargs)
        if self.date_approved or self.status == FamilyMember.STATUS_APPROVED:
            from tencent.webim import WebIM
            webim = WebIM(settings.TENCENT_WEBIM_APPID)
            webim.add_group_member(
                group_id='family_{}'.format(self.family.id),
                member_list=[dict(Member_Account=self.author.username)],
                silence=True,
            )

    def approve(self):
        # 审批通过
        self.status = FamilyMember.STATUS_APPROVED,
        self.date_approved = datetime.now()
        self.save()

    def get_watch_master_live_logs(self):
        """
        獲得觀看家族長直播的記錄
        :return:
        """
        family_master = FamilyMember.objects.filter(
            family=self.family,
            status=self.STATUS_APPROVED,
            role=self.ROLE_MASTER,
        ).first()
        assert family_master, '家族族長不存在'
        watch_logs = LiveWatchLog.objects.filter(
            author=self.author,
            live__author=family_master.author,
        )
        return watch_logs

    def watch_master_live_duration(self):
        """
        观看家族长直播时长
        :return:
        """
        duration = 0
        watch_logs = self.get_watch_master_live_logs()
        for watch_log in watch_logs:
            duration += watch_log.get_duration()
        return duration

    def watch_master_live_prize(self):
        """
        贈送給家族長的禮物數
        :return:
        """
        total_prize = 0
        watch_logs = self.get_watch_master_live_logs()
        for watch_log in watch_logs:
            total_prize += watch_log.get_total_prize()
        return total_prize

    @staticmethod
    def modify_member_title(user, member_select, title, family):
        """修改家族頭銜
            @:param member_select 要修改的成員ID数组
                    title         修改的头衔
        """
        members = FamilyMember.objects.filter(
            id__in=member_select
        )
        amount = int(Option.get('family_modify_title_coin') or 10) * members.count()
        assert user.id == family.author.id, '你不是家族族長不能修改'
        assert int(user.member.get_coin_balance()) > amount, '金幣餘額不足'
        CreditCoinTransaction.objects.create(
            user_credit=user,
            amount=amount,
            type=CreditCoinTransaction.TYPE_FAMILY_MODIFY,
            remark='家族長修改頭銜',
        )
        for member in members.all():
            member.title = title
            member.save()

        return True


class FamilyArticle(UserOwnedModel,
                    EntityModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='articles',
    )

    content = models.TextField(
        verbose_name='内容',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '家族文章'
        verbose_name_plural = '家族文章'
        db_table = 'core_family_article'

    def get_author_role(self):
        """ 返回公告作者的家族角色"""
        return FamilyMember.objects.filter(
            family=self.family,
            author=self.author,
        ).first().role


class FamilyMission(UserOwnedModel,
                    EntityModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='missions',
    )

    ITEM_WATCH_MASTER_PRIZE = 'WATCH_MASTER_PRIZE'
    ITEM_WATCH_MASTER_DURATION = 'WATCH_MASTER_DURATION'
    ITEM_COUNT_WATCH_LOG = 'COUNT_WATCH_LOG'
    ITEM_COUNT_FOLLOWED = 'COUNT_FOLLOWED'
    ITEM_COUNT_FRIEND = 'COUNT_FRIEND'
    ITEM_COUNT_LOGIN = 'COUNT_LOGIN'
    ITEM_COUNT_INVITE = 'COUNT_INVITE'
    ITEM_COUNT_SHARE_MASTER_LIVE = 'COUNT_SHARE_MASTER_LIVE'
    ITEM_COUNT_WATCH_MASTER_LIVE = 'COUNT_WATCH_MASTER_LIVE'
    ITEM_COUNT_LIVE = 'COUNT_LIVE'
    ITEM_COUNT_RECEIVE_DIAMOND = 'COUNT_RECEIVE_DIAMOND'
    ITEM_CHOICES = (
        (ITEM_WATCH_MASTER_PRIZE, '送家族长礼物额度'),
        (ITEM_WATCH_MASTER_DURATION, '观看家族长直播时长'),
        (ITEM_COUNT_WATCH_LOG, '累计观看数'),
        (ITEM_COUNT_FOLLOWED, '陌生人追踪你的个数'),
        (ITEM_COUNT_FRIEND, '拥有的好友数'),
        (ITEM_COUNT_LOGIN, '连续登录天数'),
        (ITEM_COUNT_INVITE, '邀请好友注册数'),
        (ITEM_COUNT_SHARE_MASTER_LIVE, '分享家族长直播的分享数'),
        (ITEM_COUNT_WATCH_MASTER_LIVE, '在家族长直播间的访谈数'),
        (ITEM_COUNT_LIVE, '连续开播的天数'),
        (ITEM_COUNT_RECEIVE_DIAMOND, '收到钻石额度'),
    )

    mission_item = models.CharField(
        verbose_name='任务元件',
        max_length=50,
        default=ITEM_WATCH_MASTER_PRIZE,
        choices=ITEM_CHOICES,
    )

    mission_item_value = models.IntegerField(
        verbose_name='任务元件数值',
        blank=True,
        default=0,
        help_text='指定条件达到所需的数值'
    )

    AWARD_EXPERIENCE_POINTS = 'EXPERIENCE_POINTS'
    AWARD_ICOIN = 'ICOIN'
    AWARD_COIN = 'COIN'
    AWARD_PRIZE = 'PRIZE'
    AWARD_CONTRIBUTION = 'CONTRIBUTION'
    AWARD_BADGE = 'BADGE'
    AWARD_MARQUEE_CONTENT = 'MARQUEE_CONTENT'
    AWARD_STAR = 'STAR'
    AWARD_CHOICES = (
        (AWARD_EXPERIENCE_POINTS, '经验值'),
        (AWARD_ICOIN, 'i币'),
        (AWARD_COIN, '金币'),
        (AWARD_PRIZE, '礼物'),
        (AWARD_CONTRIBUTION, '贡献值'),
        (AWARD_BADGE, '勋章'),
        (AWARD_MARQUEE_CONTENT, '跑马灯内容'),
        (AWARD_STAR, '元气'),
    )

    award_item = models.CharField(
        verbose_name='奖励元件',
        max_length=50,
        default=AWARD_EXPERIENCE_POINTS,
        choices=AWARD_CHOICES,
    )

    award_item_value = models.IntegerField(
        verbose_name='奖励元件数值',
        blank=True,
        default=0,
        help_text='指定条件达到后的奖励'
    )

    prize = models.ForeignKey(
        verbose_name='奖励礼物',
        to='Prize',
        related_name='family_missions',
        blank=True,
        null=True,
        help_text='当选择的奖励元件为礼物时添加',
    )

    badge = models.ForeignKey(
        verbose_name='奖励徽章',
        to='Badge',
        related_name='family_missions',
        blank=True,
        null=True,
        help_text='当选择的奖励元件为徽章时添加',
    )

    date_begin = models.DateField(
        verbose_name='任务开始时间',
        blank=True,
        null=True,
    )

    date_end = models.DateField(
        verbose_name='任务结束时间',
        blank=True,
        null=True,
    )

    content = models.TextField(
        verbose_name='内容(規則)',
        blank=True,
        default='',
    )

    logo = models.OneToOneField(
        verbose_name='任务海报',
        to=ImageModel,
        related_name='family_mission',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '家族任务'
        verbose_name_plural = '家族任务'
        db_table = 'core_family_mission'

    def is_end(self):
        return datetime.now().date() > self.date_end

    def is_begin(self):
        return datetime.now().date() > self.date_begin


class FamilyMissionAchievement(UserOwnedModel):
    mission = models.ForeignKey(
        verbose_name='任务',
        to='FamilyMission',
        related_name='achievements',
    )

    ##

    STATUS_START = 'START'
    STATUS_ACHIEVE = 'ACHIEVE'
    STATUS_FINISH = 'FINISH'
    STATUS_CHOICES = (
        (STATUS_START, '领取任务'),
        (STATUS_ACHIEVE, '完成任务未领取奖励'),
        (STATUS_FINISH, '完成任务已领取奖励'),
    )

    status = models.CharField(
        verbose_name='任务状态',
        max_length=20,
        choices=STATUS_CHOICES,
        null=True,
        blank=True,
    )

    coin_transaction = models.OneToOneField(
        verbose_name='奖励金币记录',
        to='CreditCoinTransaction',
        related_name='family_mission_achievement',
        null=True,
        blank=True,
    )

    prize_star_transaction = models.OneToOneField(
        verbose_name='奖励星星流水记录',
        to='CreditStarTransaction',
        null=True,
        blank=True,
    )

    prize_transaction = models.OneToOneField(
        verbose_name='獎勵礼物记录',
        to='PrizeTransaction',
        related_name='family_mission_achievement',
        null=True,
        blank=True,
    )

    badge_record = models.OneToOneField(
        verbose_name='奖励勋章记录',
        to='BadgeRecord',
        null=True,
        blank=True,
    )

    # todo i币 经验 贡献值 跑马灯内容


    class Meta:
        verbose_name = '家族任务成就'
        verbose_name_plural = '家族任务成就'
        db_table = 'core_family_mission_achievement'

    def save(self, *args, **kwargs):
        if not self.id:
            assert not self.mission.family.author == self.author, '家族長不能領取任務'

        super().save(*args, **kwargs)

    def check_mission_achievement(self):
        """
        检测家族任务是否已经完成
        已经完成返回 True
        """
        mission = self.mission
        mission_item = mission.mission_item
        # 当前完成额度
        condition_complete_count = 0
        if mission_item == FamilyMission.ITEM_WATCH_MASTER_PRIZE:
            # 送家族长礼物额度
            condition_complete_count = PrizeOrder.objects.filter(
                date_created__gt=mission.date_begin,
                date_created__lt=mission.date_end,
                author=self.author,
                receiver_prize_transaction__user_debit=mission.family.author,
            ).all().aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0
        elif mission_item == FamilyMission.ITEM_WATCH_MASTER_DURATION:
            # 观看家族长直播时长
            condition_complete_count = LiveWatchLog.objects.filter(
                live__date_created__gt=mission.date_begin,
                live__date_created__lt=mission.date_end,
                live__author=mission.family.author,
                author=self.author,
            ).all().aggregate(total_duration=models.Sum('duration')).get('total_duration') or 0
        elif mission_item == FamilyMission.ITEM_COUNT_WATCH_LOG:
            # 累计观看数
            condition_complete_count = LiveWatchLog.objects.filter(
                date_enter__gt=mission.date_begin,
                date_enter__lt=mission.date_end,
                author=self.author,
            ).count()
        elif mission_item == FamilyMission.ITEM_COUNT_FOLLOWED:
            # 陌生人追踪你的个数(粉丝)
            condition_complete_count = UserMark.objects.filter(
                object_id=self.author.id,
                subject='follow',
                content_type=ContentType.objects.get(model='member'),
                date_created__gt=mission.date_begin,
                date_created__lt=mission.date_end,
            ).count()
        elif mission_item == FamilyMission.ITEM_COUNT_FRIEND:
            # 拥有的好友数
            friends = User.objects.filter(
                contacts_owned__user=self.author,
                contacts_related__author=self.author,
            ).all()
            for friend in friends:
                contact = Contact.objects.filter(
                    models.Q(author=friend, user=self.author, timestamp__gt=mission.date_begin) |
                    models.Q(author=self.author, user=friend, timestamp__gt=mission.date_begin)
                ).order_by('-timestamp').exists()
                if contact:
                    condition_complete_count += 1
        elif mission_item == FamilyMission.ITEM_COUNT_LOGIN:
            # 连续登录天数
            date_login = mission.date_begin
            continue_login_days = 0
            while date_login <= datetime.now().date():
                if LoginRecord.objects.filter(author=self.author, date_login__date=date_login).exists():
                    # 连续登录天数
                    continue_login_days += 1
                else:
                    continue_login_days = 0
                date_login += timedelta(days=1)
                if continue_login_days == mission.mission_item_value:
                    condition_complete_count = continue_login_days
                    break
        elif mission_item == FamilyMission.ITEM_COUNT_INVITE:
            # 邀请好友注册数
            condition_complete_count = Member.objects.filter(
                date_created__gt=mission.date_begin,
                referrer=self.author,
            ).count()
        elif mission_item == FamilyMission.ITEM_COUNT_SHARE_MASTER_LIVE:
            # 分享家族长直播的分享数
            condition_complete_count = 0
        elif mission_item == FamilyMission.ITEM_COUNT_WATCH_MASTER_LIVE:
            # 在家族长直播间的访谈数
            condition_complete_count = Comment.objects.filter(
                lives__date_created__gt=mission.date_begin,
                lives__date_created__lt=mission.date_end,
                lives__author=mission.family.author,
            ).count()
        elif mission_item == FamilyMission.ITEM_COUNT_LIVE:
            # 连续开播的天数
            date_live = mission.date_begin
            continue_live_days = 0
            while date_live <= datetime.now().date():
                if Live.objects.filter(author=self.author, date_created__date=continue_live_days).exists():
                    # 连续登录天数
                    continue_live_days += 1
                else:
                    continue_live_days = 0
                date_live += timedelta(days=1)
                if continue_live_days == mission.mission_item_value:
                    condition_complete_count = continue_live_days
                    break
        elif mission_item == FamilyMission.ITEM_COUNT_RECEIVE_DIAMOND:
            # 收到钻石额度
            condition_complete_count = PrizeOrder.objects.filter(
                diamond_transaction__user_debit=self.author,
                date_created__gt=mission.date_begin,
            ).all().aggregate(amount=models.Sum("diamond_transaction__amount")).get('amount') or 0

        if condition_complete_count >= self.mission.mission_item_value:
            self.status = FamilyMissionAchievement.STATUS_ACHIEVE
            self.save()
            return True
        return False


class LiveCategory(EntityModel):
    class Meta:
        verbose_name = '直播分类'
        verbose_name_plural = '直播分类'
        db_table = 'core_live_category'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改直播分類')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增直播分類')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(user, AdminLog.TYPE_DELETE, self, '刪除直播分類')
        super().delete(*args, **kwargs)


class Live(UserOwnedModel,
           EntityModel,
           GeoPositionedModel,
           CommentableModel,
           UserMarkableModel,
           InformableModel):
    category = models.ForeignKey(
        verbose_name='直播分类',
        to='LiveCategory',
        related_name='lives',
        blank=True,
        null=True,
    )

    quota = models.IntegerField(
        verbose_name='上限观众人数',
        default=0,
        help_text='上限观众人数，0为不做限制',
    )

    password = models.CharField(
        verbose_name='房间密码',
        max_length=45,
        null=True,
        blank=True,
    )

    date_end = models.DateTimeField(
        verbose_name='结束时间',
        null=True,
        blank=True,
    )

    is_private = models.BooleanField(
        verbose_name='是否隐藏',
        default=False,
        help_text='如果设置隐藏，将不能在外部列表查询到此直播',
    )

    paid = models.IntegerField(
        verbose_name='收費',
        default=0,
    )

    is_free = models.BooleanField(
        verbose_name='是否免费',
        default=True,
    )

    hot_rating = models.IntegerField(
        verbose_name='热门指数',
        default=0,
    )

    like_count = models.IntegerField(
        verbose_name='点赞数量',
        default=0,
    )

    is_index_recommended = models.BooleanField(
        verbose_name='是否为首次推荐',
        default=False,
    )

    is_hot_recommended = models.BooleanField(
        verbose_name='是否为热门推荐',
        default=False,
    )

    class Meta:
        verbose_name = '直播'
        verbose_name_plural = '直播'
        db_table = 'core_live'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改直播')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增直播')
        else:
            super().save(*args, **kwargs)
        # WebIM 建群
        from tencent.webim import WebIM
        webim = WebIM(settings.TENCENT_WEBIM_APPID)
        webim.create_group(
            self.author.username,
            'Live_{}'.format(self.id),
            type=WebIM.GROUP_TYPE_PRIVATE,
            group_id='live_{}'.format(self.id),
        )

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(user, AdminLog.TYPE_DELETE, self, '刪除直播')

    def get_comment_count(self):
        return self.comments.count()

    def get_view_count(self):
        return LiveWatchLog.objects.filter(
            live=self.id
        ).count()

    def get_prize_count(self):
        return PrizeOrder.objects.filter(
            live_watch_log__live=self.id
        ).count()

    def get_duration(self):
        """
        直播持續時間（單位：分鐘）
        :return:
        """
        # TODO: 要充分考慮中途中斷的情況能夠正確計算直播和觀看的持續時間
        time_end = self.date_end or datetime.now()
        return int((time_end - self.date_created).seconds / 60) + \
               (time_end - self.date_created).days * 1440 or 1

    def get_live_status(self):
        if self.date_end:
            return 'OVER'
        return 'ACTION'

    # 標記一個點贊
    def set_like_by(self, user, is_like=True):
        self.set_marked_by(user, 'like', is_like)

    def is_liked_by_current_user(self):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_anonymous:
            return False
        return self.is_marked_by(user, 'like')

    def get_like_count(self):
        return self.get_users_marked_with('like').count()

    # 标记一个关注
    def set_followed_by(self, user, is_follow=True):
        self.set_marked_by(user, 'follow', is_follow)

    def is_followed_by(self, user):
        return self.is_marked_by(user, 'follow')

    def is_followed_by_current_user(self):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_anonymous:
            return False
        return self.is_followed_by(user)

    def get_followed(self):
        return Member.objects.filter(
            user__usermarks_owned__content_type=ContentType.objects.get(
                app_label=type(self)._meta.app_label,
                model=type(self)._meta.model_name,
            ),
            user__usermarks_owned__object_id=self.pk,
            user__usermarks_owned__subject='follow',
        )

    def get_room_id(self):
        from hashlib import md5
        return md5('live_{}'.format(self.pk).encode()).hexdigest()

    def get_push_url(self):
        """ 獲取推流地址
        :return:
        """
        # 只有主播和管理員用戶纔可以獲取推流地址
        from django_base.middleware import get_request
        user = get_request().user
        if not user.is_staff and \
                not user.is_superuser and \
                not user == self.author:
            return None

        # 生成推流地址
        from time import time
        from hashlib import md5
        room_id = self.get_room_id()
        biz_id = settings.TENCENT_MLVB_BIZ_ID
        live_code = biz_id + '_' + room_id
        key = settings.TENCENT_MLVB_PUSH_KEY
        # 自動有效期 1 天
        tx_time = hex(int(time()) + 24 * 3600)[2:].upper()
        tx_secret = md5((key + live_code + tx_time).encode()).hexdigest()
        return 'rtmp://{biz_id}.livepush.myqcloud.com/live/' \
               '{live_code}?bizid={biz_id}' \
               '&txSecret={tx_secret}&txTime={tx_time}' \
            .format(biz_id=biz_id, live_code=live_code,
                    tx_secret=tx_secret, tx_time=tx_time)

    def get_play_url(self):
        """ 獲取播放地址（FLV)
        :return:
        """
        room_id = self.get_room_id()
        biz_id = settings.TENCENT_MLVB_BIZ_ID
        live_code = biz_id + '_' + room_id
        return 'http://{biz_id}.liveplay.myqcloud.com/live/' \
               '{live_code}.flv' \
            .format(biz_id=biz_id, live_code=live_code)

    def get_live_diamond(self):
        """直播间获得钻石数
        """
        return PrizeOrder.objects.filter(
            live_watch_log__in=self.watch_logs.all(),
            diamond_transaction__id__gt=0,
        ).aggregate(
            amount=models.Sum('diamond_transaction__amount')
        ).get('amount') or 0

    def get_live_receiver_star(self):
        """直播间获得星光指数
        """
        return PrizeOrder.objects.filter(
            live_watch_log__in=self.watch_logs.all(),
            receiver_star_index_transaction__id__gt=0,
        ).aggregate(
            amount=models.Sum('receiver_star_index_transaction__amount')
        ).get('amount') or 0


class LiveBarrage(UserOwnedModel,
                  AbstractMessageModel):
    TYPE_BARRAGE = 'BARRAGE'
    TYPE_SMALL_EFFECT = 'SMALL_EFFECT'
    TYPE_LARGE_EFFECT = 'LARGE_EFFECT'
    TYPE_CHOICES = (
        (TYPE_BARRAGE, '弹幕'),
        (TYPE_SMALL_EFFECT, '小型特效'),
        (TYPE_LARGE_EFFECT, '大型特效'),
    )

    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='barrages',
    )

    date_sent = models.DateTimeField(
        verbose_name='发送时间',
        auto_now_add=True,
    )

    credit_coin_transaction = models.OneToOneField(
        verbose_name='扣除金幣記錄',
        to='CreditCoinTransaction',
        blank=True,
        null=True,
        related_name='barrage',
    )

    class Meta:
        verbose_name = '直播弹幕'
        verbose_name_plural = '直播弹幕'
        db_table = 'core_live_barrage'

    def save(self, *args, **kwargs):
        if not self.credit_coin_transaction:
            price = int(Option.get('coin_barrage_cost') or 1)
            if self.author.member.get_coin_balance() < price:
                raise ValidationError('金幣不足，無法發送彈幕')
            self.credit_coin_transaction = CreditCoinTransaction.objects.create(
                user_credit=self.author,
                type=CreditCoinTransaction.TYPE_BARRAGE,
                amount=price,
                remark='在直播#{}中發送彈幕'.format(self.live.id),
            )
        super().save(*args, **kwargs)


class LiveWatchLog(UserOwnedModel,
                   CommentableModel):
    """ 直播观看记录
    每次进入房间到退出房间是一次记录
    然后评论是与直播共享的
    """

    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='watch_logs',
    )

    date_enter = models.DateTimeField(
        verbose_name='进入时间',
    )

    date_leave = models.DateTimeField(
        verbose_name='退出时间',
        blank=True,
        null=True,
    )

    duration = models.IntegerField(
        verbose_name='停留時長',
        default=0,
        help_text='單位（分鐘）'
    )

    STATUS_NORMAL = 'NORMAL'
    STATUS_SILENT = 'SILENT'
    STATUS_SPEAK = 'SPEAK'
    STATUS_CHOICES = (
        (STATUS_NORMAL, '正常'),
        (STATUS_SILENT, '禁言'),
        (STATUS_SPEAK, '连麦'),
    )

    status = models.CharField(
        verbose_name='狀態',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NORMAL,
    )

    class Meta:
        verbose_name = '直播观看记录'
        verbose_name_plural = '直播观看记录'
        db_table = 'core_live_watch_log'

    def __str__(self):
        return '{} - {}'.format(
            self.author.member.mobile,
            self.live.name,
        )

    def save(self, *args, **kwargs):
        """
        自动将人加入到群组中
        :param args:
        :param kwargs:
        :return:
        """
        super().save(*args, **kwargs)
        from tencent.webim import WebIM
        webim = WebIM(settings.TENCENT_WEBIM_APPID)
        webim.add_group_member(
            group_id='live_{}'.format(self.live_id),
            member_list=[dict(Member_Account=self.author.username)],
            silence=True,
        )

    def get_comment_count(self):
        return self.comments.count()

    @staticmethod
    def enter_live(user, live):
        """
        用戶進入某直播間時執行
        :param user: 用戶
        :param live: 直播
        :return:
        """
        live_watch_log = LiveWatchLog.objects.filter(
            author=user,
            live=live,
        ).first()
        if not live_watch_log:
            LiveWatchLog.objects.create(
                author=user,
                live=live,
                date_enter=datetime.now(),
            )
        else:
            live_watch_log.date_enter = datetime.now()
            live_watch_log.save()

    def leave_live(self):
        """
        用戶離開某直播間時執行
        :return:
        """
        self.date_leave = datetime.now()
        self.duration += int((self.date_leave - self.date_enter).seconds / 60) + \
                         (self.date_leave - self.date_enter).days * 1440 or 1

        self.save()

        # 累計觀看時間
        wathch_mission_preferences = self.author.preferences.filter(key='watch_mission_time').first()
        mission_achivevments = self.author.starmissionachievements_owned.filter(
            type=StarMissionAchievement.TYPE_WATCH,
            date_created__gt=self.date_enter).order_by('-date_created')
        if mission_achivevments.exists():
            wathch_mission_preferences.value = int(wathch_mission_preferences.value) + \
                                               (datetime.now() - mission_achivevments.first().date_created).seconds
        else:
            wathch_mission_preferences.value = int(wathch_mission_preferences.value) + (
                self.date_leave - self.date_enter).seconds
        wathch_mission_preferences.save()

    def get_duration(self):
        if self.duration:
            return self.duration
        return int((datetime.now() - self.date_enter).seconds / 60) + \
               (datetime.now() - self.date_enter).days * 1440 or 1

    def get_total_prize(self):
        """
        獲取在當前直播間消費金幣
        :return:
        """
        # TODO: 未兌換成臺幣
        total_price = 0
        prize_orders = PrizeOrder.objects.filter(live_watch_log=self)
        for prize_order in prize_orders:
            total_price += prize_order.prize.price
        return total_price


class ActiveEvent(UserOwnedModel,
                  AbstractMessageModel,
                  CommentableModel,
                  UserMarkableModel,
                  InformableModel):
    """ 个人动态
    理论上只发图文，但是支持完整的消息格式
    用户可以点赞，使用 UserMark 的 subject=like
    """
    date_created = models.DateTimeField(
        verbose_name='創建時間',
        auto_now_add=True,
    )

    is_active = models.BooleanField(
        verbose_name='是否有效',
        default=True,
    )

    like_count = models.IntegerField(
        verbose_name='点赞数',
        default=0,
    )

    class Meta:
        verbose_name = '个人动态'
        verbose_name_plural = '个人动态'
        db_table = 'core_active_event'

    # 標記一個點贊
    def set_like_by(self, user, is_like=True):
        self.set_marked_by(user, 'like', is_like)

    def is_liked_by_current_user(self):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_anonymous:
            return False
        return self.is_marked_by(user, 'like')

    def get_comment_count(self):
        return self.comments.count()

    def get_like_count(self):
        return self.get_users_marked_with('like').count()

    def get_preview(self):
        if self.images.first():
            return self.images.first()

    def update_like_count(self):
        self.like_count = self.get_like_count()
        self.save()


class PrizeCategory(EntityModel):
    is_vip_only = models.BooleanField(
        verbose_name='是否VIP专属',
        default=False,
    )

    class Meta:
        verbose_name = '礼物分类'
        verbose_name_plural = '礼物分类'
        db_table = 'core_prize_category'

    def get_count_prize(self):
        return self.prizes.all().count()

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改禮物分類')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增禮物分類')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除禮物分類',
            )
        super().delete(*args, **kwargs)


class Prize(EntityModel):
    icon = models.OneToOneField(
        verbose_name='图标',
        to=ImageModel,
        related_name='prize_as_icon',
        null=True,
        blank=True,
    )

    stickers = models.ManyToManyField(
        verbose_name='表情包',
        to=ImageModel,
        related_name='prizes_as_stickers',
        blank=True,
    )

    date_sticker_begin = models.DateField(
        verbose_name='表情包有效期开始',
        blank=True,
        null=True,
    )

    date_sticker_end = models.DateField(
        verbose_name='表情包有效期结束',
        blank=True,
        null=True,
    )

    price = models.IntegerField(
        verbose_name='价格（金币/元气）',
        default=0,
    )

    PRICE_TYPE_COIN = 'COIN'
    PRICE_TYPE_STAR = 'STAR'
    PRICE_TYPE_CHOICES = (
        (PRICE_TYPE_COIN, '金币'),
        (PRICE_TYPE_STAR, '元气'),
    )

    price_type = models.CharField(
        verbose_name='价格单位',
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default=PRICE_TYPE_COIN,
    )

    TYPE_NORMAL = 'NORMAL'
    TYPE_SPECIAL = 'SPECIAL'
    TYPE_CHOICES = (
        (TYPE_NORMAL, '普通款'),
        (TYPE_SPECIAL, '特殊款'),
    )

    type = models.CharField(
        verbose_name='礼物类型',
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_NORMAL,
    )

    MARQUEE_LARGE = 'LARGE'
    MARQUEE_MEDIUM = 'MEDIUM'
    MARQUEE_SMALL = 'SMALL'
    MARQUEE_CHOICES = (
        (MARQUEE_LARGE, '大'),
        (MARQUEE_MEDIUM, '中'),
        (MARQUEE_SMALL, '小'),
    )
    marquee_size = models.CharField(
        verbose_name='跑马灯大小',
        max_length=20,
        choices=MARQUEE_CHOICES,
        default=MARQUEE_SMALL,
    )

    marquee_image = models.OneToOneField(
        verbose_name='跑马灯图案',
        to=ImageModel,
        related_name='prize_as_marquee',
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        verbose_name='礼物分类',
        to='PrizeCategory',
        related_name='prizes',
        blank=True,
        null=True,
    )

    star_box_quantity = models.IntegerField(
        verbose_name='元氣寶盒抽中數量',
        default=0,
        help_text='此禮物在元氣寶盒中出現時的贈送數量，０爲不會在元氣寶盒中出現'
    )

    class Meta:
        verbose_name = '礼物'
        verbose_name_plural = '礼物'
        db_table = 'core_prize'

    def get_balance(self, user, source_tag):
        """ 返回某個用戶對這個禮物的存量
        :param user:
        :param source_tag: 來源標籤
        :return:
        """
        # 計算當前用戶該項禮品的餘額
        # 獲得該禮物的數量
        accept = user.prizetransactions_debit.filter(
            prize=self,
            source_tag=source_tag,
        ).aggregate(amount=models.Sum('amount')).get('amount') or 0
        # 消費該禮物的數量
        send = user.prizetransactions_credit.filter(
            prize=self,
            source_tag=source_tag,
        ).aggregate(amount=models.Sum('amount')).get('amount') or 0
        # 返回餘額
        return accept - send

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        super().save(*args, **kwargs)
        if user.is_staff and self.id and not self.is_del:
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改禮物')
        elif user.is_staff and not self.is_del:
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增禮物')

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除禮物',
            )
        super().delete(*args, **kwargs)

    def get_activity_prize_balance(self, user, source_tag):
        """
        user 获得这个活动礼物的剩余数量
        source_tag 礼物来源 ACTIVITY STAR_BOX VIP
        """
        receive_count = PrizeTransaction.objects.filter(
            prize=self,
            user_credit=None,
            user_debit=user,
            source_tag=source_tag,
        ).all().aggregate(amount=models.Sum('amount')).get('amount') or 0
        send_count = PrizeTransaction.objects.filter(
            prize=self,
            user_debit=None,
            user_credit=user,
            source_tag=source_tag,
        ).all().aggregate(amount=models.Sum('amount')).get('amount') or 0
        return receive_count - send_count


class PrizeTransaction(AbstractTransactionModel):
    prize = models.ForeignKey(
        verbose_name='礼物',
        to='Prize',
        related_name='transactions',
    )

    TYPE_LIVE_RECEIVE = 'LIVE_RECEIVE'
    TYPE_LIVE_SEND_BUY = 'LIVE_SEND_BUY'
    TYPE_LIVE_SEND_BAG = 'LIVE_SEND_BAG'
    TYPE_ACTIVITY_GAIN = 'ACTIVITY_GAIN'
    TYPE_STAR_BOX_GAIN = 'STAR_BOX_GAIN'
    TYPE_VIP_GAIN = 'STAR_VIP_GAIN'
    TYPE_CHOICES = (
        (TYPE_LIVE_RECEIVE, '直播獲得'),
        (TYPE_LIVE_SEND_BUY, '直播赠送-購買'),
        (TYPE_LIVE_SEND_BAG, '直播贈送-揹包'),
        (TYPE_ACTIVITY_GAIN, '活動獲得'),
        (TYPE_STAR_BOX_GAIN, '元氣寶盒獲得'),
        (TYPE_VIP_GAIN, 'VIP回馈獲得'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    SOURCE_TAG_ACTIVITY = 'ACTIVITY'
    SOURCE_TAG_STAR_BOX = 'STAR_BOX'
    SOURCE_TAG_VIP = 'VIP'
    SOURCE_TAG_SHOP = 'SHOP'
    SOURCE_TAG_CHOICES = (
        (SOURCE_TAG_ACTIVITY, '活動禮物'),
        (SOURCE_TAG_STAR_BOX, '寶盒禮物'),
        (SOURCE_TAG_VIP, 'VIP回饋禮物'),
        (SOURCE_TAG_SHOP, '商店購買'),
    )
    source_tag = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=SOURCE_TAG_CHOICES,
    )

    # prize_count = models.IntegerField(
    #     verbose_name='礼物数量',
    #     default=1
    # )

    class Meta:
        verbose_name = '礼物记录'
        verbose_name_plural = '礼物记录'
        db_table = 'core_prize_transaction'

        # @staticmethod
        # def viewer_open_starbox(user_id):
        #     me = User.objects.get(pk=user_id)
        #     # todo 这里应该用送了多少礼物的元气
        #     assert me.member.get_star_balance() >= 500, '你的元氣不足，不能打開寶盒'
        #     prize = Prize.objects.filter(
        #         category__name='宝盒礼物',
        #         is_active=True,
        #     ).order_by('?').first()
        #     assert prize, '暫無禮物可選'
        #     # todo: 数量
        #     # 礼物记录
        #     me.prizetransactions_debit.create(
        #         prize=prize,
        #         amount=prize.price,
        #         remark='打開星光寶盒獲得禮物',
        #     )
        #     # todo: -500消耗了的元气值 应该要增加一个宝盒记录
        #     # # 元气流水
        #     # me.creditstartransactions_credit.create(
        #     #     amount=500,
        #     # )


class PrizeOrder(UserOwnedModel):
    """ 礼物订单，关联到用户在哪个直播里面购买了礼物，需要关联到对应的礼物转移记录
    ### 如果是在直播界面直接購買並贈送禮物
    禮物是即時購買並贈送的，會涉及下列的動作：
    1. 添加禮物記錄（主播和觀衆雙方記錄，但是禮物數餘額本質上沒有增加）
      1.1 添加 receiver_prize_transaction，user_debit 是 主播， user_credit 也是主播
      1.2 添加 sender_prize_transaction，user_debit 是 觀衆， user_credit 也是觀衆
    2. （如果礼物是金币礼物：PRICE_TYPE=COIN）
      2.1. 添加 CoinTransaction，user_debit 是 None，user_credit 是 送禮的觀衆用戶
      2.2. 添加 DiamondTransaction，user_debit 是 主播，user_credit 是 None
    3. （如果礼物是元气礼物：PRICE_TYPE=STAR）
      3.1. 添加 StarTransaction，user_debit 是 None，user_credit 是 送禮的觀衆用戶（扣除元气）
      3.2. 添加 StarIndexSenderTransaction，user_debit None，user_credit 是 观众
      3.3. 添加 StarIndexReceiverTransaction，user_debit 是 主播，user_credit 是 None
    4. 添加 PrizeOrder，關聯上述流水

    ### 如果是在活動或者元氣寶盒中獲得禮物獎勵
    1. 添加 PrizeTransaction，user_debit 是 獲得獎勵的用戶，user_credit 是 None

    ### 如果在直播中上使用活動獎勵或者元氣寶盒中獲得的禮物（揹包中的禮物）
    1. 添加禮物記錄（主播和觀衆雙方記錄，主播沒有實際獲得禮物餘額，但觀衆的禮物餘額被扣除）
      1.1 添加 receiver_prize_transaction，user_debit 是 主播， user_credit 也是主播
      1.2 添加 sender_prize_transaction，user_debit 是 None， user_credit 是觀衆（註銷禮物）
    2. （如果礼物是金币礼物：PRICE_TYPE=COIN）
      2.1. 添加 DiamondTransaction，user_debit 是 主播，user_credit 是 None
    3. （如果礼物是元气礼物：PRICE_TYPE=STAR）
      3.1. 添加 StarIndexSenderTransaction，user_debit None，user_credit 是 观众
      3.2. 添加 StarIndexReceiverTransaction，user_debit 是 主播，user_credit 是 None
    4. 添加 PrizeOrder，關聯上述流水
    """
    prize = models.ForeignKey(
        verbose_name='礼物',
        to='Prize',
        related_name='orders',
    )

    live_watch_log = models.ForeignKey(
        verbose_name='观看记录',
        to='LiveWatchLog',
        related_name='prize_orders',
    )

    receiver_prize_transaction = models.OneToOneField(
        verbose_name='礼物记录',
        to='PrizeTransaction',
        related_name='prize_orders_as_receiver',
        null=True,
        blank=True,
    )

    sender_prize_transaction = models.OneToOneField(
        verbose_name='礼物记录',
        to='PrizeTransaction',
        related_name='prize_orders_as_sender',
        null=True,
        blank=True,
    )

    coin_transaction = models.OneToOneField(
        verbose_name='金幣消費记录',
        to='CreditCoinTransaction',
        related_name='prize_orders',
        null=True,
        blank=True,
    )

    diamond_transaction = models.OneToOneField(
        verbose_name='主播鑽石记录',
        to='CreditDiamondTransaction',
        related_name='prize_orders',
        null=True,
        blank=True,
    )

    star_transaction = models.OneToOneField(
        verbose_name='观众消耗元氣记录',
        to='CreditStarTransaction',
        related_name='prize_orders',
        null=True,
        blank=True,
    )

    receiver_star_index_transaction = models.OneToOneField(
        verbose_name='主播元气指數记录',
        to='CreditStarIndexReceiverTransaction',
        related_name='prize_orders',
        null=True,
        blank=True,
    )

    sender_star_index_transaction = models.OneToOneField(
        verbose_name='觀衆元气指數记录',
        to='CreditStarIndexSenderTransaction',
        related_name='prize_orders',
        null=True,
        blank=True,
    )

    date_created = models.DateTimeField(
        verbose_name='创建时间',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = '礼物订单'
        verbose_name_plural = '礼物订单'
        db_table = 'core_prize_order'

    @staticmethod
    def buy_prize(live, prize, count, user):
        """ 在直播中直接購買禮物並且送出
        :param live:
        :param prize:
        :param count:
        :param user:
        :return:
        """
        # 獲取直播記錄
        watch_log = live.watch_logs.filter(author=user).first()
        assert watch_log, '用戶還沒有進入直播觀看，不能購買禮物贈送'

        total_price = count * prize.price

        # 校驗餘額是否充足
        if prize.price_type == Prize.PRICE_TYPE_COIN:
            assert user.member.get_coin_balance() >= total_price, '赠送失败,金幣余额不足'
        elif prize.price_type == Prize.PRICE_TYPE_STAR:
            assert user.member.get_star_balance() >= total_price, '赠送失败,元氣不足'
        else:
            raise AssertionError('不正確的禮物支付類型')

        # 礼物流水
        receiver_prize_transaction = PrizeTransaction.objects.create(
            amount=count,
            user_debit=live.author,
            user_credit=live.author,
            remark='收到用戶贈送的禮物(直播#{}-直接購買)'.format(live.id),
            prize=prize,
            type=PrizeTransaction.TYPE_LIVE_RECEIVE,
            source_tag=PrizeTransaction.SOURCE_TAG_SHOP,
        )
        sender_prize_transaction = PrizeTransaction.objects.create(
            amount=count,
            user_debit=user,
            user_credit=user,
            remark='贈送禮物給主播(直播#{}-直接購買)'.format(live.id),
            prize=prize,
            type=PrizeTransaction.TYPE_LIVE_SEND_BUY,
            source_tag=PrizeTransaction.SOURCE_TAG_SHOP,
        )

        coin_transaction = None
        diamond_transaction = None
        if prize.price_type == Prize.PRICE_TYPE_COIN:
            # 金币流水
            coin_transaction = CreditCoinTransaction.objects.create(
                user_credit=user,
                amount=total_price,
                type=CreditCoinTransaction.TYPE_LIVE_GIFT,
                remark='購買禮物',
            )
            # 钻石流水
            diamond_transaction = CreditDiamondTransaction.objects.create(
                user_debit=live.author,
                amount=total_price,
                remark='禮物兌換',
                type=CreditDiamondTransaction.TYPE_LIVE_GIFT,
            )

        star_transaction = None
        receiver_star_index_transaction = None
        sender_star_index_transaction = None
        if prize.price_type == Prize.PRICE_TYPE_STAR:
            star_transaction = CreditStarTransaction.objects.create(
                user_credit=user,
                amount=total_price,
                remark='購買禮物',
                type=CreditStarTransaction.TYPE_LIVE_GIFT,
            )
            receiver_star_index_transaction = CreditStarIndexReceiverTransaction.objects.create(
                user_debit=user,
                amount=total_price,
                remark='直播贈送禮物產生',
                type=CreditStarIndexReceiverTransaction.TYPE_GENERATE,
            )
            sender_star_index_transaction = CreditStarIndexSenderTransaction.objects.create(
                user_debit=user,
                amount=total_price,
                remark='直播贈送禮物產生',
                type=CreditStarIndexSenderTransaction.TYPE_GENERATE,
            )

        # 礼物订单
        order = PrizeOrder.objects.create(
            author=user,
            prize=prize,
            live_watch_log=watch_log,
            receiver_prize_transaction=receiver_prize_transaction,
            sender_prize_transaction=sender_prize_transaction,
            coin_transaction=coin_transaction,
            diamond_transaction=diamond_transaction,
            star_transaction=star_transaction,
            receiver_star_index_transaction=receiver_star_index_transaction,
            sender_star_index_transaction=sender_star_index_transaction,
        )

        # 更新主播徽章
        live.author.member.add_diamond_badge()

        # todo
        # 檢測當日購買這個禮物類型夠不夠送桌布

        return order

    @staticmethod
    def send_active_prize(live, prize, count, user, source_tag):
        """ 在直播中送出揹包中的禮物
        :param live:
        :param prize:
        :param count:
        :param user:
        :param source_tag: 禮物的來源編號，不同的禮物來源賬戶是分開的
        :return:
        """
        # 獲取直播記錄
        watch_log = live.watch_logs.filter(author=user).first()
        assert watch_log, '用戶還沒有進入直播觀看，不能購買禮物贈送'

        total_price = count * prize.price
        assert int(prize.get_balance(user, source_tag)) >= count, '贈送失敗，禮物剩餘不足'
        # 礼物流水
        receiver_prize_transaction = PrizeTransaction.objects.create(
            amount=count,
            user_debit=live.author,
            user_credit=live.author,
            remark='收到用戶贈送的禮物(直播#{}-揹包贈送)'.format(live.id),
            prize=prize,
            type=PrizeTransaction.TYPE_LIVE_RECEIVE,
            source_tag=source_tag,
        )
        sender_prize_transaction = PrizeTransaction.objects.create(
            amount=count,
            user_debit=None,
            user_credit=user,
            remark='贈送禮物給主播(直播#{}-揹包贈送)'.format(live.id),
            prize=prize,
            type=PrizeTransaction.TYPE_LIVE_SEND_BAG,
            source_tag=source_tag,
        )

        diamond_transaction = None
        if prize.price_type == Prize.PRICE_TYPE_COIN:
            # 钻石流水
            diamond_transaction = CreditDiamondTransaction.objects.create(
                user_debit=live.author,
                amount=total_price,
                remark='禮物兌換',
                type=CreditDiamondTransaction.TYPE_LIVE_GIFT,
            )

        receiver_star_index_transaction = None
        sender_star_index_transaction = None
        if prize.price_type == Prize.PRICE_TYPE_STAR:
            receiver_star_index_transaction = CreditStarIndexReceiverTransaction.objects.create(
                user_credit=user,
                amount=total_price,
                remark='直播贈送禮物產生',
                type=CreditStarIndexReceiverTransaction.TYPE_GENERATE,
            )
            sender_star_index_transaction = CreditStarIndexSenderTransaction.objects.create(
                user_credit=user,
                amount=total_price,
                remark='直播贈送禮物產生',
                type=CreditStarIndexSenderTransaction.TYPE_GENERATE,
            )

        # 礼物订单
        order = PrizeOrder.objects.create(
            author=user,
            prize=prize,
            live_watch_log=watch_log,
            receiver_prize_transaction=receiver_prize_transaction,
            sender_prize_transaction=sender_prize_transaction,
            coin_transaction=None,
            diamond_transaction=diamond_transaction,
            star_transaction=None,
            receiver_star_index_transaction=receiver_star_index_transaction,
            sender_star_index_transaction=sender_star_index_transaction,
        )

        # 更新主播徽章
        live.author.member.add_diamond_badge()

        return order


class RankRecord(UserOwnedModel):
    DURATION_DATE = 'DATE'
    DURATION_WEEK = 'WEEK'
    DURATION_TOTAL = 'TOTAL'
    DURATION_CHOICES = (
        (DURATION_DATE, '每日'),
        (DURATION_WEEK, '每週'),
        (DURATION_TOTAL, '統計'),
    )

    duration = models.CharField(
        verbose_name='統計區間',
        max_length=20,
        choices=DURATION_CHOICES,
    )

    receive_diamond_amount = models.DecimalField(
        verbose_name='收到钻石數量',
        decimal_places=2,
        max_digits=18,
    )

    send_diamond_amount = models.DecimalField(
        verbose_name='送出钻石數量',
        decimal_places=2,
        max_digits=18,
    )

    star_index_amount = models.DecimalField(
        verbose_name='元气指数',
        decimal_places=2,
        max_digits=18,
    )

    class Meta:
        verbose_name = '排行榜記錄'
        verbose_name_plural = '排行榜記錄'
        db_table = 'core_rank_record'

    def __str__(self):
        return '{}:{}'.format(self.author, self.get_duration_display())

    def update(self):
        now = datetime.now()
        am5 = datetime(now.year, now.month, now.day, 5, 0)
        tomorrow_am5 = am5 + timedelta(days=1)
        weekday = now.weekday()
        monday = am5 - timedelta(days=weekday)
        sunday = am5 + timedelta(days=7 - weekday)
        # 日榜重置
        if self.duration == self.DURATION_DATE and (now - am5).total_seconds() > 0 and (
                    now - am5).total_seconds() < 900:
            self.receive_diamond_amount = 0
            self.send_diamond_amount = 0
            self.star_index_amount = 0
            self.save()
        # 周榜重置
        elif self.duration == self.DURATION_WEEK and weekday == 0 and (now - am5).total_seconds() > 0 and (
                    now - am5).total_seconds() < 900:
            self.receive_diamond_amount = 0
            self.send_diamond_amount = 0
            self.star_index_amount = 0
            self.save()
        elif self.duration == self.DURATION_TOTAL:
            self.receive_diamond_amount = PrizeOrder.objects.filter(
                diamond_transaction__user_debit=self.author,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            self.send_diamond_amount = PrizeOrder.objects.filter(
                author=self.author,
                diamond_transaction__id__gt=0,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            credit = self.author.creditstarindexreceivertransactions_credit.aggregate(
                amount=models.Sum('amount')).get('amount') or 0
            debit = self.author.creditstarindexreceivertransactions_debit.aggregate(
                amount=models.Sum('amount')).get('amount') or 0
            self.star_index_amount = debit - credit
            self.save()
        elif self.duration == self.DURATION_DATE:
            self.receive_diamond_amount = PrizeOrder.objects.filter(
                diamond_transaction__user_debit=self.author,
                date_created__gt=am5,
                date_created__lt=tomorrow_am5,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            self.send_diamond_amount = PrizeOrder.objects.filter(
                author=self.author,
                diamond_transaction__id__gt=0,
                date_created__gt=am5,
                date_created__lt=tomorrow_am5,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            credit = PrizeOrder.objects.filter(
                author=self.author,
                sender_star_index_transaction__id__gt=0,
                date_created__gt=am5,
                date_created__lt=tomorrow_am5,
            ).aggregate(amount=models.Sum('sender_star_index_transaction__amount')).get('amount') or 0

            debit = PrizeOrder.objects.filter(
                author=self.author,
                receiver_star_index_transaction__id__gt=0,
                date_created__gt=am5,
                date_created__lt=tomorrow_am5,
            ).aggregate(amount=models.Sum('receiver_star_index_transaction__amount')).get('amount') or 0
            self.star_index_amount = debit - credit
            self.save()

        elif self.duration == self.DURATION_WEEK:
            self.receive_diamond_amount = PrizeOrder.objects.filter(
                diamond_transaction__user_debit=self.author,
                date_created__gt=monday,
                date_created__lt=sunday,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            self.send_diamond_amount = PrizeOrder.objects.filter(
                author=self.author,
                diamond_transaction__id__gt=0,
                date_created__gt=monday,
                date_created__lt=sunday,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 0

            credit = PrizeOrder.objects.filter(
                author=self.author,
                sender_star_index_transaction__id__gt=0,
                date_created__gt=monday,
                date_created__lt=sunday,
            ).aggregate(amount=models.Sum('sender_star_index_transaction__amount')).get('amount') or 0

            debit = PrizeOrder.objects.filter(
                author=self.author,
                receiver_star_index_transaction__id__gt=0,
                date_created__gt=monday,
                date_created__lt=sunday,
            ).aggregate(amount=models.Sum('receiver_star_index_transaction__amount')).get('amount') or 0
            self.star_index_amount = debit - credit
            self.save()

    @staticmethod
    def make(member):
        RankRecord.objects.create(
            author=member.user,
            duration=RankRecord.DURATION_DATE,
            receive_diamond_amount=0,
            send_diamond_amount=0,
            star_index_amount=0,
        )
        RankRecord.objects.create(
            author=member.user,
            duration=RankRecord.DURATION_WEEK,
            receive_diamond_amount=0,
            send_diamond_amount=0,
            star_index_amount=0,
        )
        RankRecord.objects.create(
            author=member.user,
            duration=RankRecord.DURATION_TOTAL,
            receive_diamond_amount=0,
            send_diamond_amount=0,
            star_index_amount=0,
        )


class ExtraPrize(EntityModel):
    """ 赠送礼物
    购买礼物包超过N个金币，赠送给对应的用户一张壁纸
    不需要实际产生赠送记录，根据用户消费额筛选以获得可以下载的壁纸列表
    """

    prize_category = models.ForeignKey(
        verbose_name='礼物分類',
        to='PrizeCategory',
        related_name='extra_prizes',
        null=True,
        blank=True,
    )

    required_amount = models.IntegerField(
        verbose_name='需要的单日金币消费额',
    )

    wallpaper = models.OneToOneField(
        verbose_name='壁纸',
        to=ImageModel,
        related_name='extra_prize_as_wallpaper',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '附赠礼物'
        verbose_name_plural = '附赠礼物'
        db_table = 'core_extra_prize'

        # todo 每次用戶购买礼物就检测当天购买这个礼物分类额度，发放礼物，注意重复发送


class StatisticRule(EntityModel):
    """ TODO: 统计规则
    用于统计用户在某一时间段内是否满足某些统计条件
    """

    date_begin = models.DateTimeField(
        verbose_name='开始时间',
    )

    date_end = models.DateTimeField(
        verbose_name='结束时间',
    )

    class Meta:
        verbose_name = '统计规则'
        verbose_name_plural = '统计规则'
        db_table = 'core_rule'

    def examine(self, user):
        """ TODO: 返回用户是否满足统计的规则
        :param user:
        :return: bool
        """
        raise NotImplemented()


class Activity(EntityModel):
    """ 活动
    具体的规则JSON存放在rules字段中，具体规则如下

    [VOTE 票选活动]
    {
        prize: <Prize.id>, // 得票方式（统计获得的物品编号）
        awards: [{
            from: 1,  // 奖励的名次区间
            to: 3,
            award: {
                type: '', // experience:经验值/icoin:i币/coin:金币/star:星星/prize:礼物/contribution:贡献值/badge:勋章
                value: , // 奖励值，如果是点数类即为奖励的点数，礼物或勋章则对应编号
            },
        }, {
            ...
        }], # 奖励方式
    }

    [WATCH 观看直播活动]
    {
        min_watch: 最小观看数
        min_duration: 每次观看需要的时长
        award: {
            type: '', // experience:经验值/icoin:i币/coin:金币/star:星星/prize:礼物/contribution:贡献值/badge:勋章
            value: , // 奖励值，如果是点数类即为奖励的点数，礼物或勋章则对应编号
        },
    }

    [DRAW 抽奖活动]
    {
        condition_code: '000001', // 抽奖资格编号
        condition_value: 1, // 需要达到的数量
        awards: [{ // 数组共 8 个区间，下面按顺序描述八个区间的内容
            weight: 0.125, // 概率权重
            award: {
                type: '', // experience:经验值/icoin:i币/coin:金币/star:星星/prize:礼物/contribution:贡献值/badge:勋章
                value: , // 奖励值，如果是点数类即为奖励的点数，礼物或勋章则对应编号
            },
        }]
    }
    * 所有 condition：
    000001 - 送礼物额度
    000002 - 观看直播时长
    000003 - 累计观看数
    000004 - 追踪数
    000005 - 好友数
    000006 - 粉丝数
    000007 - 分享直播间数
    000008 - 邀请好友注册数
    000009 - 连续登入X天
    000010 - 连续开播X天
    000011 - 收到钻石额度

    [DIAMOND 累计钻石活动]
    {
        awards: [{
            from: 10000,  // 钻石要求数区间
            to: 30000,
            award: {
                type: '', // experience:经验值/icoin:i币/coin:金币/star:星星/prize:礼物/contribution:贡献值/badge:勋章
                value: , // 奖励值，如果是点数类即为奖励的点数，礼物或勋章则对应编号
            },
        }, {
            ...
        }], # 奖励方式
    }
    """
    TYPE_VOTE = 'VOTE'
    TYPE_WATCH = 'WATCH'
    TYPE_DRAW = 'DRAW'
    TYPE_DIAMOND = 'DIAMOND'
    TYPE_CHOICES = (
        (TYPE_VOTE, '票选'),
        (TYPE_WATCH, '观看直播'),
        (TYPE_DRAW, '抽奖'),
        (TYPE_DIAMOND, '累计钻石'),
    )

    type = models.CharField(
        verbose_name='活动类型',
        max_length=20,
        default=TYPE_VOTE,
        choices=TYPE_CHOICES,
    )

    thumbnail = models.OneToOneField(
        verbose_name='活动海报',
        to=ImageModel,
        related_name='activity',
        null=True,
        blank=True,
    )

    content = models.TextField(
        verbose_name='内容',
        blank=True,
        default='',
    )

    rules = models.TextField(
        verbose_name='规则参数',
        blank=True,
        default='',
        help_text='存放规则的JSON',
    )

    # vote_prize = models.ForeignKey(
    #     verbose_name='统计礼物',
    #     to='Prize',
    #     help_text='仅对票选类活动有效，活动期间获得此礼物的数量将作为统计数量',
    # )

    # rule = models.TextField(
    #     verbose_name='规则',
    #     blank=True,
    #     default='',
    #     help_text='''
    #     【票选类】
    #     统计
    #     {"prize": <int:prize_id>, "amount": <int:min_amount>,
    #     "award": ???}
    #     【观看直播类】
    #     数量统计，JSON 描述：
    #     {"0": 0, "10": 50, "50": 300, "100": 500} 表示：
    #     10-50 次观看奖励 50 个金币；
    #     50-100 次观看奖励 300 个金币；
    #     100+ 次观看奖励 500 个金币；
    #     【抽奖活动】
    #     {}
    #     ''',
    # )

    date_begin = models.DateTimeField(
        verbose_name='开始时间',
    )

    date_end = models.DateTimeField(
        verbose_name='结束时间',
    )

    is_settle = models.BooleanField(
        verbose_name='是否已结算',
        default=False,
    )

    class Meta:
        verbose_name = '活动'
        verbose_name_plural = '活动'
        db_table = 'core_activity'

        # def clean(self):
        #     if self.type == self.TYPE_VOTE and not self.vote_prize:
        #         raise ValidationError('票选活动必须指定礼品')
        #     if self.type != self.TYPE_VOTE and self.vote_prize:
        #         raise ValidationError('非票选活动不可以指定礼品')
        #     if self.type == self.TYPE_WATCH:
        #         try:
        #             watch_rule = json.loads(self.watch_rule)
        #             for key, value in sorted(watch_rule.items()):
        #                 assert re.match(r'^\d+$', key)
        #                 assert type(value) == int
        #         except:
        #             raise ValidationError('观看类活动参数设置不正确')

    def status(self):
        """
        活動進行狀態 （NOTSTART:未開始、BEGIN:進行中、END:已結束）
        """
        now = datetime.now()
        if now < self.date_begin:
            return 'NOTSTART'
        elif now > self.date_end:
            return 'END'
        return 'BEGIN'

    def vote_way(self):
        """
        票選活動 得票方式
        """
        if not self.type == self.TYPE_VOTE:
            return None
        rule = json.loads(self.rules)
        if self.type == self.TYPE_VOTE and rule['prize']:
            prize_id = rule['prize']
            prize = Prize.objects.filter(id=prize_id).first()
            if prize:
                return prize.name
        return None

    def vote_count_award(self):
        """
        票選活動 獲獎名額
        """
        if not self.type == self.TYPE_VOTE:
            return None
        rule = json.loads(self.rules)
        if rule['awards']:
            data = []
            for award in rule['awards']:
                data.append(award['to'] - award['from'] + 1)
            return sum(data) or 0
        return 0

    def watch_min_watch(self):
        """
        觀看直播活動 最小觀看數
        """
        if not self.type == self.TYPE_WATCH:
            return None
        rule = json.loads(self.rules)
        if rule['min_watch']:
            return rule['min_watch']
        return 0

    def watch_min_duration(self):
        """
        觀看直播活動 每次觀看需要的時長
        """
        if not self.type == self.TYPE_WATCH:
            return None
        rule = json.loads(self.rules)
        if rule['min_duration']:
            return rule['min_duration']
        return 0

    def draw_condition_code(self):
        """
        抽奖活动 返回抽奖资格编号
        """
        if not self.type == self.TYPE_DRAW:
            return None
        rule = json.loads(self.rules)
        if rule['condition_code']:
            return rule['condition_code']
        return None

    def draw_condition_value(self):
        """
        抽奖活动 返回需要达到的数量
        :return:
        """
        if not self.type == self.TYPE_DRAW:
            return None
        rule = json.loads(self.rules)
        if rule['condition_value']:
            return rule['condition_value']
        return 0

    def award_way(self):
        """
        获奖方式
        :return:
        """
        rule = json.loads(self.rules)
        string = []
        str_rank = ''
        str_weight = ''
        str_award = ''
        if self.type == self.TYPE_VOTE:
            for award_item in rule['awards']:
                if award_item['from'] == award_item['to']:
                    str_rank = '第{}名：'.format(award_item['from'])
                else:
                    str_rank = '第{}名 - 第{}名：'.format(award_item['from'], award_item['to'])
                if award_item['award']['type'] == 'badge':
                    badge = Badge.objects.filter(id=award_item['award']['value']).first()
                    if badge:
                        str_award = badge.name + '徽章'
                elif award_item['award']['type'] == 'prize':
                    prize = Prize.objects.filter(id=award_item['award']['value']).first()
                    if prize:
                        str_award = prize.name + '禮物'
                else:
                    str_award = '{}{}'.format(
                        award_item['award']['value'],
                        self.award_type_format(award_item['award']['type'])
                    )
                string.append(str_rank + str_award)
            return string
        if self.type == self.TYPE_WATCH:
            if rule['award']['type'] == 'badge':
                badge = Badge.objects.filter(id=rule['award']['value']).first()
                if badge:
                    str_award = badge.name
            elif rule['award']['type'] == 'prize':
                prize = Prize.objects.filter(id=rule['award']['value']).first()
                if prize:
                    str_award = prize.name
            else:
                str_award = '{}{}'.format(
                    rule['award']['value'],
                    self.award_type_format(rule['award']['type'])
                )
            string.append(str_award)
            return string
        if self.type == self.TYPE_DRAW:
            for award_item in rule['awards']:
                str_weight = '權重：({}) -  '.format(award_item['weight'])
                if award_item['award']['type'] == 'badge':
                    badge = Badge.objects.filter(id=award_item['award']['value']).first()
                    if badge:
                        str_award = badge.name
                elif award_item['award']['type'] == 'prize':
                    prize = Prize.objects.filter(id=award_item['award']['value']).first()
                    if prize:
                        str_award = prize.name
                else:
                    str_award = '  {}{}'.format(
                        award_item['award']['value'],
                        self.award_type_format(award_item['award']['type'])
                    )
                string.append(str_weight + str_award)
            return string
        if self.type == self.TYPE_DIAMOND:
            for award_item in rule['awards']:
                if award_item['from'] == award_item['to']:
                    str_rank = '{}鑽石'.format(award_item['from'])
                else:
                    str_rank = '{} - {}鑽石：'.format(award_item['from'], award_item['to'])
                if award_item['award']['type'] == 'badge':
                    badge = Badge.objects.filter(id=award_item['award']['value']).first()
                    if badge:
                        str_award = badge.name
                elif award_item['award']['type'] == 'prize':
                    prize = Prize.objects.filter(id=award_item['award']['value']).first()
                    if prize:
                        str_award = prize.name
                else:
                    str_award = '  {}{}'.format(
                        award_item['award']['value'],
                        self.award_type_format(award_item['award']['type'])
                    )
                string.append(str_rank + str_award)
            return string
        return None

    @staticmethod
    def award_type_format(type):
        if type == 'experience':
            return '經驗值'
        elif type == 'icoin':
            return 'i幣'
        elif type == 'coin':
            return '金幣'
        elif type == 'star':
            return '元氣'
        elif type == 'contribution':
            return '貢獻值'
        return None

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改活動')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增活動')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除活動',
            )
        super().delete(*args, **kwargs)

    def settle(self):
        """ 结算当次活动，找出所有参与记录，然后统计满足条件的自动发放奖励
            跑批用，每天执行1次
            转盘活动  過期結算，不做任何獎勵流水 is_settle = True
            钻石活动  過期結算，不做任何獎勵流水 is_settle = True
            观看任务  全部用户，在结束日期之后做一次结算，全部用户排序结算 is_settle = True
            投票活动  全部用户，在结束日期之后做一次结算，全部用户排序结算 is_settle = True
        :return:
        """
        rules = json.loads(self.rules)
        if datetime.now() < self.date_end or self.is_settle:
            # 活动没结束 或者 活动已经结束 不做结算动作
            return
        if self.type == Activity.TYPE_WATCH:
            # 观看任务结算
            awards = rules['award']
            watch_logs = LiveWatchLog.objects.filter(
                live__date_created__gt=self.date_begin,
                live__date_created__lt=self.date_end,
                duration__gt=rules['min_duration'],
            ).all()
            members = Member.objects.filter(
                user__in=[watch_log.author for watch_log in watch_logs],
            ).all()
            for member in members:
                logs_count = member.user.livewatchlogs_owned.filter(
                    live__date_created__gt=self.date_begin,
                    live__date_created__lt=self.date_end,
                    duration__gt=rules['min_duration'],
                ).count()
                if logs_count >= int(rules['min_watch']):
                    # 符合条件的会员，添加奖励和参加活动记录
                    member.member_activity_award(self, awards)
        if self.type == Activity.TYPE_VOTE:
            # 投票活动
            awards = rules['awards']
            # members: 活动时间内所有会员按收到礼物排序
            members = Member.objects.extra(
                select=dict(
                    prize_amount="""
                        select sum(t.amount)
                        from  core_prize_transaction t, core_prize_order o, core_activity a
                        where user_id = t.user_debit_id and user_id = t.user_credit_id
                        and t.prize_id = {prize_id} and a.id = {activity_id}
                        and o.receiver_prize_transaction_id = t.id
                        and o.date_created >= a.date_begin and o.date_created <= a.date_end
                    """.format(prize_id=rules['prize'], activity_id=self.id)
                )).order_by('-prize_amount').all()
            # 活动奖励列表
            for award in awards:
                # 其中一项奖励将from 和 to组成一个range范围，members[i]范围内的会员
                for i in range(int(award['from']) - 1, int(award['to'])):
                    try:
                        if members[i].prize_amount:
                            members[i].member_activity_award(self, award['award'])
                    except Exception as e:
                        print(e)
        # 转盘活动 或者鑽石活動 直接改結算狀態
        self.is_settle = True
        self.save()
        return

    def date_end_countdown(self):
        """ 活动倒计时，返回分钟
        """
        if self.date_end < datetime.now():
            return 0
        return int((self.date_end - datetime.now()).seconds / 60) + \
               (self.date_end - datetime.now()).days * 1440

    def join_draw_activity(self, user):
        """ 参与抽獎活动
            判断用户是否满足活动参与条件，满足就创建活动参与记录，状态为进行中
        """
        assert datetime.now() > self.date_begin, '活動還沒開始'
        assert datetime.now() < self.date_end and not self.is_settle, '活動已結束'
        assert not ActivityParticipation.objects.filter(author=user, activity=self).exists(), '您已經參與過抽獎'

        condition = json.loads(self.rules)
        # 活动条件完成数量。到达活动所规定的数量才能参与活动
        condition_complete_count = 0

        if json.loads(self.rules)['condition_code'] == '000001':
            # 送禮額度
            condition_complete_count = PrizeOrder.objects.filter(
                coin_transaction__user_credit=user,
                date_created__gt=self.date_begin,
            ).all().aggregate(amount=models.Sum("coin_transaction__amount")).get('amount') or 0
        elif json.loads(self.rules)['condition_code'] == '000002':
            # 觀看時長
            condition_complete_count = LiveWatchLog.objects.filter(
                author=user,
                live__date_created__gt=self.date_begin,
                live__date_created__lt=self.date_end,
            ).all().aggregate(total_duration=models.Sum('duration')).get('total_duration') or 0
        elif json.loads(self.rules)['condition_code'] == '000003':
            # 累計觀看數
            condition_complete_count = LiveWatchLog.objects.filter(
                date_enter__gt=self.date_begin,
                author=user,
            ).count()
        elif json.loads(self.rules)['condition_code'] == '000004':
            # 追蹤數
            condition_complete_count = UserMark.objects.filter(
                author=user,
                subject='follow',
                content_type=ContentType.objects.get(model='member'),
                date_created__gt=self.date_begin,
            ).count()
        elif condition['condition_code'] == '000005':
            # 好友數
            friends = User.objects.filter(
                contacts_owned__user=user,
                contacts_related__author=user
            ).all()
            for friend in friends:
                contact = Contact.objects.filter(
                    models.Q(author=friend, user=user, timestamp__gt=self.date_begin) |
                    models.Q(author=user, user=friend, timestamp__gt=self.date_begin)
                ).order_by('-timestamp').exists()
                if contact:
                    condition_complete_count += 1
        elif condition['condition_code'] == '000006':
            # 粉絲數
            condition_complete_count = UserMark.objects.filter(
                object_id=user.id,
                subject='follow',
                content_type=ContentType.objects.get(model='member'),
                date_created__gt=self.date_begin,
            ).count()
        elif json.loads(self.rules)['condition_code'] == '000007':
            # 分享直播間數
            # todo
            print(1)
        elif condition['condition_code'] == '000008':
            # 邀請好友註冊數
            condition_complete_count = Member.objects.filter(
                date_created__gt=self.date_begin,
                referrer=user).count()
        elif json.loads(self.rules)['condition_code'] == '000009':
            # 連續登入X天
            # 從活動開始第一日起连续登录
            date_login = self.date_begin.date()
            continue_login_days = 0
            while date_login <= datetime.now().date():
                if LoginRecord.objects.filter(author=user, date_login__date=date_login).exists():
                    # 连续登录天数
                    continue_login_days += 1
                else:
                    continue_login_days = 0
                date_login += timedelta(days=1)
                if continue_login_days == condition['condition_value']:
                    # 连续登录天数
                    condition_complete_count = continue_login_days
                    break
        elif condition['condition_code'] == '000010':
            # 連續開播X天
            date_live = self.date_begin.date()
            continue_live_days = 0
            while date_live <= datetime.now().date():
                if Live.objects.filter(author=user, date_created=date_live).exists():
                    # 连续登录
                    continue_live_days += 1
                else:
                    continue_live_days = 0
                date_live += timedelta(days=1)
                if continue_live_days == condition['condition_value']:
                    # 连续开播达到条件
                    condition_complete_count = continue_live_days
                    break
        elif condition['condition_code'] == '000011':
            # 收到鑽石額度
            condition_complete_count = PrizeOrder.objects.filter(
                diamond_transaction__user_debit=user,
                date_created__gt=self.date_begin,
            ).all().aggregate(amount=models.Sum("diamond_transaction__amount")).get('amount') or 0
        if condition_complete_count < condition['condition_value']:
            return False
        return True

    def draw_activity_award(self):
        """
           前段用，输出抽奖活动各区域的奖励
        """
        if not self.type == Activity.TYPE_DRAW:
            return False
        rules = json.loads(self.rules)
        # print(rules['awards'])
        data = []
        award_type = dict(
            coin='金幣',
            diamond='鑽石',
            experience='經驗值',
            icoin='i幣',
            star='元氣',
            contribution='貢獻值',
        )
        for award_item in rules['awards']:
            award = award_item['award']
            if not award['type'] == 'prize' and not award['type'] == 'badge':
                data.append('{} {}'.format(award['value'], award_type[award['type']]))
            elif award['type'] == 'prize':
                prize = Prize.objects.get(pk=award['value'])
                data.append('禮物:{}'.format(prize.name))
            elif award['type'] == 'badge':
                badge = Badge.objects.get(pk=award['value'])
                data.append('徽章:{}'.format(badge.name))
            else:
                data.append('')
        return data


class ActivityPage(EntityModel):
    banner = models.ForeignKey(
        verbose_name='海报',
        to=ImageModel,
        related_name='activity_pages',
    )

    activity = models.ForeignKey(
        verbose_name='活动',
        to='Activity',
        related_name='pages',
    )

    remark = models.TextField(
        verbose_name='备注',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '活动页'
        verbose_name_plural = '活动页'
        db_table = 'core_activity_page'


class ActivityParticipation(UserOwnedModel):
    activity = models.ForeignKey(
        verbose_name='活动',
        to='Activity',
        related_name='participations',
    )

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_COMPLETE = 'COMPLETE'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, '进行中'),
        (STATUS_EXPIRED, '超时未达成'),
        (STATUS_COMPLETE, '完成'),
    )

    status = models.CharField(
        verbose_name='参与状态',
        max_length=20,
        default=STATUS_ACTIVE,
        choices=STATUS_CHOICES,
    )

    coin_transaction = models.OneToOneField(
        verbose_name='金币奖励记录',
        to='CreditCoinTransaction',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    diamond_transaction = models.OneToOneField(
        verbose_name='钻石奖励记录',
        to='CreditDiamondTransaction',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    prize_transaction = models.OneToOneField(
        verbose_name='礼物奖励记录',
        to='PrizeTransaction',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    star_transaction = models.OneToOneField(
        verbose_name='元气奖励记录',
        to='CreditStarTransaction',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    badge_record = models.OneToOneField(
        verbose_name='奖励徽章记录',
        to='BadgeRecord',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    experience_transaction = models.ForeignKey(
        verbose_name='经验流水',
        to='ExperienceTransaction',
        related_name='activity_participation',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '活动参与记录'
        verbose_name_plural = '活动参与记录'
        db_table = 'core_activity_participation'
        # 同一用户不能多次参与同一个活动
        unique_together = [('activity', 'author')]


class Notifications(UserOwnedModel):
    """ 用户通知
    如果用户收到了点赞、评论、追踪等会收到通知
    """

    class Meta:
        verbose_name = '通知'
        verbose_name_plural = '通知'
        db_table = 'core_notification'


class VisitLog(UserOwnedModel,
               GeoPositionedModel):
    user = models.ForeignKey(
        verbose_name='被访问用户',
        to=User,
        related_name='visit_logs',
    )

    date_last_visit = models.DateTimeField(
        verbose_name='最后访问时间',
        auto_now=True,
    )

    @staticmethod
    def visit(guest, host):
        """ 记录 Guest 用户对 Host 用户的一次访问
        :param guest: 访问的用户
        :param host: 被访问的用户
        :return:
        """
        log, created = VisitLog.objects.get_or_create(
            author=guest.user,
            user=host.user,
        )
        log.date_created = datetime.now()
        log.geo_lat = guest.geo_lat
        log.geo_lng = guest.geo_lng
        log.geo_label = guest.geo_label
        log.save()

    def time_ago(self):
        return int((datetime.now() - self.date_last_visit).seconds / 60) + \
               (datetime.now() - self.date_last_visit).days * 1440

    class Meta:
        verbose_name = '访客记录'
        verbose_name_plural = '访客记录'
        db_table = 'core_visit_log'


class Movie(UserOwnedModel,
            UserMarkableModel,
            EntityModel):
    """ 影片节目
    可以通过 UserMark subject=like/visit 等进行用户标记
    """
    thumbnail = models.OneToOneField(
        verbose_name='封面图片',
        to=ImageModel,
        related_name='movie',
        null=True,
        blank=True,
    )

    embed_link = models.URLField(
        verbose_name='嵌入链接',
    )

    tag_name = models.CharField(
        verbose_name='标签名称',
        max_length=100,
        blank=True,
        default='',
    )

    tag_color = models.CharField(
        verbose_name='标签颜色',
        max_length=20,
        default='#FF0000',
    )

    CATEGORY_HOT = 'HOT'
    CATEGORY_SPECIAL = 'SPECIAL'
    CATEGORY_CHOICES = (
        (CATEGORY_HOT, '热门视频'),
        (CATEGORY_SPECIAL, '特辑视频'),
    )

    category = models.CharField(
        verbose_name='影片分类',
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=True,
        default='',
    )

    TYPE_MOVIE = 'MOVIE'
    TYPE_LIVE = 'LIVE'
    TYPE_CHOICES = (
        (TYPE_MOVIE, '影片'),
        (TYPE_LIVE, '直播'),
    )

    type = models.CharField(
        verbose_name='類型',
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
        default='',
        help_text='當影片分類爲熱門視頻時需要選擇',
    )

    content = models.TextField(
        verbose_name='内容',
        blank=True,
        default='',
    )

    view_count = models.IntegerField(
        verbose_name='播放次数',
        default=0,
    )

    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='movies',
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = '影片节目'
        verbose_name_plural = '影片节目'
        db_table = 'core_movie'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改影片節目')
        elif user.is_staff and not self.is_del:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增影片節目')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除影片節目',
            )
        super().delete(*args, **kwargs)


class StarBox(EntityModel):
    class Meta:
        verbose_name = '星光宝盒'
        verbose_name_plural = '星光宝盒'
        db_table = 'core_star_box'


class StarBoxRecord(UserOwnedModel):
    """ 用户获得星光宝盒的记录 """
    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='star_box_records',
    )

    # star_box = models.ForeignKey(
    #     verbose_name='星光宝盒',
    #     to='StarBox',
    #     related_name='records',
    # )

    date_created = models.DateTimeField(
        verbose_name='获得时间',
        auto_now_add=True,
    )

    receiver_star_index_transaction = models.OneToOneField(
        verbose_name='主播元气指數记录',
        to='CreditStarIndexReceiverTransaction',
        related_name='star_box_records',
        null=True,
        blank=True,
    )

    sender_star_index_transaction = models.OneToOneField(
        verbose_name='觀衆元气指數记录',
        to='CreditStarIndexSenderTransaction',
        related_name='star_box_records',
        null=True,
        blank=True,
    )

    prize_transaction = models.OneToOneField(
        verbose_name='礼物记录',
        to='PrizeTransaction',
        related_name='star_box_record',
        null=True,
        blank=True,
    )

    coin_transaction = models.OneToOneField(
        verbose_name='金幣记录',
        to='CreditCoinTransaction',
        related_name='star_box_record',
        null=True,
        blank=True,
    )

    diamond_transaction = models.OneToOneField(
        verbose_name='鑽石记录',
        to='CreditDiamondTransaction',
        related_name='star_box_record',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '星光宝盒记录'
        verbose_name_plural = '星光宝盒记录'
        db_table = 'core_star_box_record'

    @staticmethod
    def open_star_box(user, live, identity):
        """开星光宝盒
        identity = 'receiver' 主播開盒
        identity = 'sender'   观众开盒
        """

        # 随机奖励 0->金币，１->钻石，2->礼物
        award = random.randint(0, 2)
        coin_debit = None
        diamond_debit = None
        prize_debit = None
        if award == 0:
            # 金幣
            amount = random.randint(int(Option.get('min_star_box_coin') or 100),
                                    int(Option.get('max_star_box_coin') or 500))
            coin_debit = CreditCoinTransaction.objects.create(
                user_debit=user,
                amount=amount,
                remark='元气宝盒开启金币',
                type=CreditCoinTransaction.TYPE_BOX
            )
        elif award == 1:
            # 鑽石
            amount = random.randint(int(Option.get('min_star_box_diamond') or 100),
                                    int(Option.get('max_star_box_diamond') or 500))
            diamond_debit = CreditDiamondTransaction.objects.create(
                user_debit=user,
                amount=amount,
                remark='元气宝盒开启钻石',
                type=CreditDiamondTransaction.TYPE_BOX
            )
        elif award == 2:
            # 禮物
            prize_option = json.loads(Option.get(key='star_box_prize_list') or '[]')
            assert len(prize_option) > 0, '沒有寶盒禮物列表，請等待寶盒禮物設置後重新抽獎'
            prize_num = random.randint(0, len(prize_option) - 1)
            prize_award = prize_option[prize_num]
            prize = Prize.objects.get(pk=prize_award['prize'])
            prize_debit = PrizeTransaction.objects.create(
                user_debit=user,
                amount=prize_award['amount'],
                remark='打開寶盒贈送禮物',
                prize=prize,
                type=PrizeTransaction.TYPE_STAR_BOX_GAIN,
                source_tag=PrizeTransaction.SOURCE_TAG_STAR_BOX,
            )

        # 元气指数消耗
        receiver_star_credit = None
        sender_star_credit = None
        if identity == 'receiver':
            assert user.member.get_star_index_receiver_balance() > 500, '打開寶盒失敗:你的元氣指數不夠,請再努力直播!'
            receiver_star_credit = CreditStarIndexReceiverTransaction.objects.create(
                user_credit=user,
                amount=500,
                remark='主播打开元气宝盒',
                type=CreditStarIndexReceiverTransaction.TYPE_BOX_EXPENSE,
            )
        elif identity == 'sender':
            assert user.member.get_star_index_sender_balance() > 500, '打開寶盒失敗:你的元氣指數不夠,請再努力直播!'
            sender_star_credit = CreditStarIndexSenderTransaction.objects.create(
                user_credit=user,
                amount=500,
                remark='觀衆開元氣寶盒',
                type=CreditStarIndexSenderTransaction.TYPE_BOX_EXPENSE,
            )
        else:
            return False

        box_record = StarBoxRecord.objects.create(
            author=user,
            live=live,
            receiver_star_index_transaction=receiver_star_credit,
            sender_star_index_transaction=sender_star_credit,
            coin_transaction=coin_debit,
            diamond_transaction=diamond_debit,
            prize_transaction=prize_debit,
        )
        return box_record


class RedBagRecord(UserOwnedModel):
    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='red_bag_records',
    )

    # TODO: type 红包发放的币种
    # TODO: transaction 红包发放对应的交易流水
    # TODO: is_opened 是否已领取
    class Meta:
        verbose_name = '红包记录'
        verbose_name_plural = '红包记录'
        db_table = 'core_red_bag_record'


# class StarMission(EntityModel):
#     # TODO: 实现规则的数据化
#     class Meta:
#         verbose_name = '星光任务'
#         verbose_name_plural = '星光任务'
#         db_table = 'core_star_mission'


class StarMissionAchievement(UserOwnedModel):
    # mission = models.ForeignKey(
    #     verbose_name='任务',
    #     to='StarMission',
    #     related_name='achievements',
    # )

    TYPE_WATCH = 'WATCH'
    TYPE_SHARE = 'SHARE'
    TYPE_INVITE = 'INVITE'
    TYPE_INFORMATION = 'INFORMATION'
    TYPE_CHOICES = (
        (TYPE_WATCH, '观看直播30分钟'),
        (TYPE_SHARE, '分享直播间'),
        (TYPE_INVITE, '邀请好友'),
        (TYPE_INFORMATION, '完善个人资料'),
    )

    type = models.CharField(
        verbose_name='任务类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    points = models.IntegerField(
        verbose_name='获得星光点数',
        default=0,
    )

    date_created = models.DateTimeField(
        verbose_name='创建时间',
        auto_now_add=True,
    )

    # live = models.ForeignKey(
    #     verbose_name='直播',
    #     to='Live',
    #     related_name='star_mission_achievement',
    #     null=True,
    #     blank=True,
    # )

    # TODO: 领取之后的关联流水

    class Meta:
        verbose_name = '星光任务成果'
        verbose_name_plural = '星光任务成果'
        db_table = 'core_star_mission_achievement'


class LevelOption(models.Model):
    class Meta:
        verbose_name = '等级设定'
        verbose_name_plural = '等级设定'
        db_table = 'core_level_option'


class Inform(UserOwnedModel,
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
        to=ImageModel,
        related_name='informs',
        blank=True,
    )

    inform_type = models.CharField(
        verbose_name='举报类型',
        max_length=50,
        blank=True,
        default='',
    )

    reason = models.TextField(
        verbose_name='举报内容',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '举报'
        verbose_name_plural = '举报'
        db_table = 'core_inform'

    def get_accused_object(self):
        if self.lives.first():
            return self.lives.first()
        elif self.activeevents.first():
            return self.activeevents.first()
        return None

    def accused_person(self):
        accused_object = self.get_accused_object()
        return dict(
            accused_id=accused_object.author.id,
            accused_mobile=accused_object.author.member.mobile,
        )

    def accused_object_info(self):
        accused_object = self.get_accused_object()
        if not accused_object:
            return None
        return dict(
            object_id=accused_object.id,
            object_type=type(accused_object)._meta.model_name,
            object_name=accused_object.name if hasattr(accused_object,
                                                       'name') else accused_object.author.member.nickname,
        )


class Feedback(AbstractMessageModel,
               UserOwnedModel):
    """ 用户反馈
    """

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
        db_table = 'core_feedback'


class Banner(models.Model):
    image = models.OneToOneField(
        verbose_name='图片',
        to=ImageModel,
        related_name='banner',
    )

    url = models.CharField(
        verbose_name='跳转链接',
        max_length=255,
        blank=True,
        default='',
        help_text='可以是直接链接或者JSON类型的路由描述'
    )

    remark = models.TextField(
        verbose_name='备注',
        blank=True,
        default='',
    )

    sorting = models.SmallIntegerField(
        verbose_name='轮播次序',
        default=0,
        help_text='数字越小越靠前',
    )

    SUBJECT_HOT = 'HOT'
    SUBJECT_VIDEO = 'VIDEO'
    SUBJECT_ACTIVITY = 'ACTIVITY'
    SUBJECT_CHOICES = (
        (SUBJECT_HOT, '热门页面'),
        (SUBJECT_VIDEO, '节目页面'),
        (SUBJECT_ACTIVITY, '活动页面'),
    )

    subject = models.CharField(
        verbose_name='主题',
        max_length=20,
        choices=SUBJECT_CHOICES,
        default='',
    )

    class Meta:
        verbose_name = '节目Banner'
        verbose_name_plural = '节目Banner'
        db_table = 'core_banner'

    def save(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff and self.id:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_UPDATE, self, '修改節目Banner')
        elif user.is_staff:
            super().save(*args, **kwargs)
            AdminLog.make(user, AdminLog.TYPE_CREATE, self, '新增節目Banner')
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除節目Banner',
            )
        super().delete(*args, **kwargs)


class SensitiveWord(models.Model):
    text = models.CharField(
        verbose_name='文本',
        max_length=255,
    )

    class Meta:
        verbose_name = '敏感词'
        verbose_name_plural = '敏感词'
        db_table = 'core_sensitive_word'


class DiamondExchangeRecord(UserOwnedModel):
    date_created = models.DateTimeField(
        verbose_name='兑换时间',
        auto_now_add=True,
    )

    diamond_count = models.IntegerField(
        verbose_name='兑换的钻石数量',
    )

    coins_count = models.IntegerField(
        verbose_name='兑换的金币数量',
    )

    diamond_transaction = models.OneToOneField(
        verbose_name='钻石交易流水',
        to='CreditDiamondTransaction',
        related_name='diamond_exchange_record',
    )

    coin_transaction = models.OneToOneField(
        verbose_name='金币交易流水',
        to='CreditCoinTransaction',
        related_name='diamond_exchange_record',
    )

    class Meta:
        verbose_name = '钻石兑换记录'
        verbose_name_plural = '钻石兑换记录'
        db_table = 'core_diamond_exchange_record'

    @staticmethod
    def diamond_exchange_coin(user, coin_count):
        # todo :比率
        diamond_count = 2 * coin_count
        assert user.member.get_diamond_balance() > diamond_count, '鑽石余额不足'

        diamond_transaction = CreditDiamondTransaction.objects.create(
            user_credit=user,
            amount=diamond_count,
            type=CreditDiamondTransaction.TYPE_EXCHANGE,
            remark='鑽石兌換金幣',
        )
        coin_transaction = CreditCoinTransaction.objects.create(
            user_debit=user,
            amount=coin_count,
            type=CreditCoinTransaction.TYPE_EXCHANGE,
            remark='鑽石兌換金幣',
        )

        record = DiamondExchangeRecord.objects.create(
            author=user,
            diamond_count=diamond_count,
            coins_count=coin_count,
            diamond_transaction=diamond_transaction,
            coin_transaction=coin_transaction,
        )

        # return record


class VirboCard(UserOwnedModel,
                EntityModel):
    image_card = models.OneToOneField(
        verbose_name='虚宝卡',
        to=ImageModel,
        related_name='virbo_cards',
        null=True,
        blank=True,
    )

    image_background = models.OneToOneField(
        verbose_name='背景图',
        to=ImageModel,
        related_name='virbo_cards_as_background',
        null=True,
        blank=True,
    )

    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = (
        (STATUS_PENDING, '未领取'),
        (STATUS_ACCEPTED, '已领取'),
        (STATUS_EXPIRED, '已过期'),
    )

    status = models.CharField(
        verbose_name='状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    validity_days = models.IntegerField(
        verbose_name='有效期',
        default=10,
        help_text='有效期天数',
    )

    class Meta:
        verbose_name = '虚宝卡'
        verbose_name_plural = '虚宝卡'
        db_table = 'core_virbo_card'
