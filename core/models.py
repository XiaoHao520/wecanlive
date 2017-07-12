from django_base.models import *
from django_member.models import *
from django_finance.models import *


# 附加到公共類上的方法

def comment_watch_status(self):
    watch_log = self.livewatchlogs.first()
    if not watch_log:
        return None
    return watch_log.status


Comment.watch_status = comment_watch_status


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

    class Meta:
        verbose_name = '会员'
        verbose_name_plural = '会员'
        db_table = 'core_member'

    def is_robot(self):
        return hasattr(self.user, 'robot') and self.user.robot

    def is_info_complete(self):
        """ TODO: 判断用户个人资料是否完善
        :return: 返回个人资料是否完善，用于星光任务统计
        """
        raise NotImplemented()

    def is_followed_by(self, user):
        return self.is_marked_by(user, 'follow')

    def is_followed_by_current_user(self):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_anonymous:
            return False
        return self.is_followed_by(user)

    # 标记一个跟踪
    def set_followed_by(self, user, is_follow=True):
        self.set_marked_by(user, 'follow', is_follow)

    def get_follow(self):
        return Member.get_objects_marked_by(self.user, 'follow')

    def get_followed(self):
        return Member.objects.filter(
            user__usermarks_owned__content_type=ContentType.objects.get(
                app_label=type(self)._meta.app_label,
                model=type(self)._meta.model_name,
            ),
            user__usermarks_owned__object_id=self.pk,
            user__usermarks_owned__subject='follow',
        )

    def get_follow_count(self):
        return self.get_follow().count().__str__()

    def get_followed_count(self):
        return self.get_followed().count().__str__()

    def get_friend_count(self):
        return Contact.objects.filter(
            author=self.user
        ).count()

    def get_live_count(self):
        return Live.objects.filter(author=self.user).count()

    def get_last_live_end(self):
        """
        最后直播时间
        :return:
        """
        last_live = Live.objects.filter(author=self.user).last()
        if not last_live:
            return None
        return str(last_live.date_end)

    def get_live_total_duration(self):
        duration = 0
        lives = Live.objects.filter(author=self.user)
        for live in lives:
            duration += live.get_duration()
        return duration

    def get_diamond_balance(self):
        # 钻石余额
        # 支出鑽石數
        credit_diamond = self.user.creditdiamondtransactions_credit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        # 收入鑽石數
        debit_diamond = self.user.creditdiamondtransactions_debit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_diamond - credit_diamond

    def get_coin_balance(self):
        # 金币余额
        # 支出金币
        credit_coin = self.user.creditcointransactions_credit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        # 收入金币
        debit_coin = self.user.creditcointransactions_debit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_coin - credit_coin

    def diamond_count(self):
        """获得钻石总数
        :return:
        """
        count = self.user.creditdiamondtransactions_debit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return int(count)

    def starlight_count(self):
        """星光指数
        :return:
        """
        count = self.user.creditstarindextransactions_debit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return int(count)

    def get_star_balance(self):
        """星星（元气）余额
        """
        credit_star = self.user.creditstartransactions_credit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0

        debit_star = self.user.creditstartransactions_debit.all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return debit_star - credit_star

    def get_star_prize_expend(self):
        """元气礼物赠送的元气数量，观众背包礼物宝盒礼物使用，每500开一个礼盒
        """

        transitions_amount = self.user.prizetransitions_credit.filter(
            prize__category__name='宝盒礼物'
        ).all().aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return transitions_amount - self.user.starboxrecords_owned.count() * 500


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


class CelebrityCategory(EntityModel):
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


class CreditStarTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '星星流水'
        verbose_name_plural = '星星流水'
        db_table = 'core_credit_star_transaction'


class CreditStarIndexTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '星光指数（元氣）流水'
        verbose_name_plural = '星光指数（元氣）流水'
        db_table = 'core_credit_star_index_transaction'


class CreditDiamondTransaction(AbstractTransactionModel):
    TYPE_LIVE_GIFT = 'LIVE_GIFT'
    TYPE_CHOICES = (
        (TYPE_LIVE_GIFT, '直播赠送'),
    )

    type = models.CharField(
        verbose_name='流水类型',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='diamond_transactions',
        null=True,
        blank=True,
    )

    live_watch_log = models.ForeignKey(
        verbose_name='直播参与记录',
        to='LiveWatchLog',
        related_name='diamond_transactions',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '钻石流水'
        verbose_name_plural = '钻石流水'
        db_table = 'core_credit_diamond_transaction'


class CreditCoinTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '金币流水'
        verbose_name_plural = '金币流水'
        db_table = 'core_credit_coin_transaction'


class Badge(UserOwnedModel,
            EntityModel):
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

    item_key = models.CharField(
        verbose_name='元件序号',
        max_length=20,
        blank=True,
        default='根据后台指定的几种任务元件的编号',
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


class DailyCheckInLog(UserOwnedModel):
    date_created = models.DateTimeField(
        verbose_name='签到时间',
        auto_now_add=True,
    )

    prize_star_transaction = models.OneToOneField(
        verbose_name='奖励星星流水记录',
        to='CreditStarTransaction',
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
        # TODO: 1. 同一天不能重复签到
        # TODO: 2. 签到之后要计算发放相应的奖励


class Family(UserOwnedModel,
             EntityModel):
    logo = models.OneToOneField(
        verbose_name='图标',
        to=ImageModel,
        related_name='family',
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


class FamilyMember(UserOwnedModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='members',
    )

    title = models.CharField(
        verbose_name='称号',
        max_length=100,
    )

    join_message = models.CharField(
        verbose_name='加入信息',
        max_length=255,
        help_text='用户在申请加入家族的时候填写的信息',
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

    class Meta:
        verbose_name = '家族成员'
        verbose_name_plural = '家族成员'
        db_table = 'core_family_member'


class FamilyArticle(UserOwnedModel,
                    EntityModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='articles',
    )

    class Meta:
        verbose_name = '家族文章'
        verbose_name_plural = '家族文章'
        db_table = 'core_family_article'


class FamilyMission(UserOwnedModel,
                    EntityModel):
    family = models.ForeignKey(
        verbose_name='家族',
        to='Family',
        related_name='missions',
    )

    class Meta:
        verbose_name = '家族任务'
        verbose_name_plural = '家族任务'
        db_table = 'core_family_mission'


class FamilyMissionAchievement(UserOwnedModel):
    mission = models.ForeignKey(
        verbose_name='任务',
        to='FamilyMission',
        related_name='achievements',
    )

    class Meta:
        verbose_name = '家族任务成就'
        verbose_name_plural = '家族任务成就'
        db_table = 'core_family_mission_achievement'


class LiveCategory(EntityModel):
    class Meta:
        verbose_name = '直播分类'
        verbose_name_plural = '直播分类'
        db_table = 'core_live_category'


class Live(UserOwnedModel,
           EntityModel,
           GeoPositionedModel,
           CommentableModel,
           UserMarkableModel,
           InformableModel):
    category = models.ForeignKey(
        verbose_name='直播分类',
        to='LiveCategory',
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

    class Meta:
        verbose_name = '直播'
        verbose_name_plural = '直播'
        db_table = 'core_live'

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

    class Meta:
        verbose_name = '直播弹幕'
        verbose_name_plural = '直播弹幕'
        db_table = 'core_live_barrage'


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
        prize_orders = PrizeOrder.objects.filter(live_watch_log=self.id)
        for prize_order in prize_orders:
            total_price += prize_order.prize.price
        return total_price

    def get_watch_mission_count(self):
        """当前用户分享当前直播间次数
        """
        return self.live.star_mission_achievement.filter(
            author=self.author,
            type='WATCH',
        ).count()


class ActiveEvent(UserOwnedModel,
                  AbstractMessageModel,
                  CommentableModel,
                  UserMarkableModel):
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


class PrizeCategory(EntityModel):
    class Meta:
        verbose_name = '礼物分类'
        verbose_name_plural = '礼物分类'
        db_table = 'core_prize_category'

    def get_prizes(self):
        prizes = []
        # todo 经验值
        for prize in self.prizes.all():
            prizes.append(dict(
                id=prize.id,
                name=prize.name,
                price=prize.price,
                icon=prize.icon.image.url,
            ))
        return prizes


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

    date_sticker_begin = models.DateTimeField(
        verbose_name='表情包有效期开始',
        blank=True,
        null=True,
    )

    date_sticker_end = models.DateTimeField(
        verbose_name='表情包有效期结束',
        blank=True,
        null=True,
    )

    price = models.IntegerField(
        verbose_name='价格（金币）',
        default=0,
    )

    MARQUEE_BIG = 'BIG'
    MARQUEE_SMALL = 'SMALL'
    MARQUEE_CHOICES = (
        (MARQUEE_BIG, '大'),
        (MARQUEE_SMALL, '小'),
    )
    marquee_size = models.CharField(
        verbose_name='跑马灯大小',
        max_length=20,
        choices=MARQUEE_CHOICES,
        default=MARQUEE_SMALL,
    )

    category = models.ForeignKey(
        verbose_name='礼物分类',
        to='PrizeCategory',
        related_name='prizes',
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = '礼物'
        verbose_name_plural = '礼物'
        db_table = 'core_prize'


class PrizeTransition(AbstractTransactionModel):
    prize = models.ForeignKey(
        verbose_name='礼物',
        to='Prize',
        related_name='transitions',
    )

    # prize_count = models.IntegerField(
    #     verbose_name='礼物数量',
    #     default=1
    # )

    class Meta:
        verbose_name = '礼物记录'
        verbose_name_plural = '礼物记录'
        db_table = 'core_prize_transition'

    @staticmethod
    def send_active_prize(live, count, prize, user_id):
        user = User.objects.get(pk=user_id)
        amount = prize.price * count
        log = live.watch_logs.filter(author=user).first()

        accept = user.prizetransitions_debit.filter(
            prize=prize,
            user_credit=None,
        ).all().aggregate(amount=models.Sum('amount')).get('amount') or 0

        send = user.prizetransitions_credit.filter(
            prize=prize,
        ).exclude(
            user_debit=None
        ).all().aggregate(amount=models.Sum('amount')).get('amount') or 0

        total = int((accept - send) / prize.price)
        assert total >= count, '贈送失敗，禮物剩餘不足'

        user.prizetransitions_credit.create(
            user_debit=live.author,
            amount=amount,
            remark=count,
            prize=prize,
        )
        # 如果是礼盒礼物不加钻石，加元气指数
        if prize.category.name == '宝盒礼物':
            starindex_transition = live.author.creditstarindextransactions_debit.create(
                amount=amount,
                remark='觀衆贈送寶盒禮物',
            )

        else:
            # 钻石流水
            diamond_transition = live.author.creditdiamondtransactions_debit.create(
                amount=amount,
                remark='禮物兌換',
                type='LIVE_GIFT',
                live=live,
                live_watch_log=log,
            )

    @staticmethod
    def viewer_open_starbox(user_id):
        me = User.objects.get(pk=user_id)
        # todo 这里应该用送了多少礼物的元气
        assert me.member.get_star_balance() >= 500, '你的元氣不足，不能打開寶盒'
        prize = Prize.objects.filter(
            category__name='宝盒礼物',
            is_active=True,
        ).order_by('?').first()
        assert prize, '暫無禮物可選'
        # todo: 数量
        # 礼物记录
        me.prizetransitions_debit.create(
            prize=prize,
            amount=prize.price,
            remark='打開星光寶盒獲得禮物',
        )
        # todo: -500消耗了的元气值 应该要增加一个宝盒记录
        # # 元气流水
        # me.creditstartransactions_credit.create(
        #     amount=500,
        # )


class PrizeOrder(UserOwnedModel):
    """ 礼物订单，关联到用户在哪个直播里面购买了礼物，需要关联到对应的礼物转移记录
    ### 如果是在直播界面直接購買並贈送禮物
    禮物是即時購買並贈送的，會涉及下列的動作：
    1. 添加 PrizeTransaction，user_debit 是 主播， user_credit 是 None
    2. 添加 CoinTransaction，user_debit 是 None，user_credit 是 送禮的觀衆用戶
    3. 添加 DiamondTransaction，user_debit 是 主播，user_credit 是 None
    4. 添加 PrizeOrder，關聯上述三條流水
    ### 如果是在活動中獲得禮物獎勵
    1. 不添加 PrizeOrder
    2. 添加 PrizeTransaction，user_debit 是 獲得獎勵的用戶，user_credit 是 None
    ### 如果在直播中上使用活動獎勵得到的禮物
    1. 不添加 PrizeOrder
    2. 添加 PrizeTransaction，user_debit 是 主播，user_credit 是 送禮的觀衆用戶
    3. 添加 DiamondTransaction，user_debit 是 主播，user_credit 是 None

    ### 如果在直播中使用宝盒礼物
    1. 不添加 PrizeOrder
    2. 添加 PrizeTransaction，user_debit 是 主播，user_credit 是 送禮的觀衆用戶
    3. 添加星光指数流水CreditStarIndexTransaction user_debit 是主播 , user_credit 是none
    4. 添加星光流水CreditStarTransaction user_debit 是none ，user_credit 是送礼的观众用户
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

    prize_transition = models.OneToOneField(
        verbose_name='礼物记录',
        to='PrizeTransition',
        related_name='prize_orders',
    )

    coin_transition = models.OneToOneField(
        verbose_name='金幣消費记录',
        to='CreditCoinTransaction',
        related_name='prize_orders',
    )

    diamond_transition = models.OneToOneField(
        verbose_name='主播鑽石记录',
        to='CreditDiamondTransaction',
        related_name='prize_orders',
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
    def buy_prize(live, prize, count, user_id):
        total_price = count * prize.price
        user = User.objects.get(pk=user_id)
        assert user.member.get_coin_balance() >= total_price, '赠送失败,余额不足'
        log = live.watch_logs.filter(author=user).first()
        # 礼物流水
        prize_transition = user.prizetransitions_credit.create(
            amount=total_price,
            user_debit=live.author,
            remark=count,
            prize=prize,
        )

        # 金币流水
        coin_transition = user.creditcointransactions_credit.create(
            amount=total_price,
            remark='購買禮物',
        )

        # 钻石流水
        diamond_transition = live.author.creditdiamondtransactions_debit.create(
            amount=total_price,
            remark='禮物兌換',
            type='LIVE_GIFT',
            live=live,
            live_watch_log=log,
        )

        # 礼物订单
        order = user.prizeorders_owned.create(
            prize=prize,
            live_watch_log=log,
            prize_transition=prize_transition,
            coin_transition=coin_transition,
            diamond_transition=diamond_transition,
        )

        return order


class ExtraPrize(EntityModel):
    """ 赠送礼物
    购买礼物包超过N个金币，赠送给对应的用户一张壁纸
    不需要实际产生赠送记录，根据用户消费额筛选以获得可以下载的壁纸列表
    """

    prize = models.ForeignKey(
        verbose_name='礼物',
        to='Prize',
        related_name='extra_prizes',
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

    def settle(self):
        """ 结算当次活动，找出所有参与记录，然后统计满足条件的自动发放奖励
        :return:
        """


class ActivityPage(models.Model):
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
        (STATUS_ACTIVE, '完成'),
    )

    status = models.CharField(
        verbose_name='参与状态',
        max_length=20,
        default=STATUS_ACTIVE,
        choices=STATUS_CHOICES,
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
            author=guest,
            user=host,
        )
        log.date_created = datetime.now()
        log.geo_lat = guest.geo_lat
        log.geo_lng = guest.geo_lng
        log.geo_label = guest.geo_label
        log.save()

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

    class Meta:
        verbose_name = '影片节目'
        verbose_name_plural = '影片节目'
        db_table = 'core_movie'


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
    star_box = models.ForeignKey(
        verbose_name='星光宝盒',
        to='StarBox',
        related_name='records',
    )

    date_created = models.DateTimeField(
        verbose_name='获得时间',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = '星光宝盒记录'
        verbose_name_plural = '星光宝盒记录'
        db_table = 'core_star_box_record'


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

    live = models.ForeignKey(
        verbose_name='直播',
        to='Live',
        related_name='star_mission_achievement',
        null=True,
        blank=True,
    )

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
