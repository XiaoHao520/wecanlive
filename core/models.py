from django_base.models import *
from django_member.models import *


# TODO: 充值和提现尚未实现


class Member(AbstractMember,
             GeoPositionedModel,
             UserMarkableModel):
    """ 会员
    注意：用户的追踪状态通过 UserMark 的 subject=follow 类型实现
    """

    class Meta:
        verbose_name = '会员'
        verbose_name_plural = '会员'
        db_table = 'core_member'


class Badge(UserOwnedModel,
            EntityModel):
    class Meta:
        verbose_name = '奖章'
        verbose_name_plural = '奖章'
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
        blank=True
    )

    class Meta:
        verbose_name = '每日签到',
        verbose_name_plural = '每日签到',
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
    users = models.ManyToManyField(
        verbose_name='家族成员',
        to='User',
        through='FamilyMember',
        through_fields=('family', 'author'),
        related_name='families',
    )

    messages = models.ManyToManyField(
        verbose_name='家族消息',
        to='Message',
        related_name='families',
    )

    class Meta:
        verbose_name = '家族'
        verbose_name_plural = '家族'
        db_table = 'core_family'


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
        db_table = 'core_family_mission'


class LiveCategory(EntityModel):
    class Meta:
        verbose_name = '直播分类'
        verbose_name_plural = '直播分类'
        db_table = 'core_live_category'


class Live(UserOwnedModel,
           EntityModel,
           CommentableModel):
    password = models.CharField(
        verbose_name='房间密码',
        max_length=45,
    )

    class Meta:
        verbose_name = '直播'
        verbose_name_plural = '直播'
        db_table = 'core_live'


class LiveBarrage(UserOwnedModel,
                  AbstractMessageModel):

    TYPE_BARRAGE = 'BARRAGE'
    TYPE_SMALL_EFFECT = 'SMALL_EFFECT'
    TYPE_LARGE_EFFECT = 'LARGE_EFFECT'
    TYPE_CHOICES =(
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


class LiveWatchLog(UserOwnedModel):
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
    )

    class Meta:
        verbose_name = '直播观看记录'
        verbose_name_plural = '直播观看记录'
        db_table = 'core_live_watch_log'


class ActiveEvent(UserOwnedModel,
                  AbstractMessageModel,
                  CommentableModel,
                  UserMarkableModel):
    """ 个人动态
    理论上只发图文，但是支持完整的消息格式
    用户可以点赞，使用 UserMark 的 subject=like
    """

    class Meta:
        verbose_name = '个人动态'
        verbose_name_plural = '个人动态'
        db_table = 'core_active_event'


class Prize(EntityModel):
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

    class Meta:
        verbose_name = '礼物记录'
        verbose_name_plural = '礼物记录'
        db_table = 'core_prize_transition'


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
        default=STATUS_ACTIVE,
        choices=STATUS_CHOICES,
    )

    class Meta:
        verbose_name = '活动参与记录'
        verbose_name_plural = '活动参与记录'
        db_table = 'core_activity_participation'
        # 同一用户不能多次参与同一个活动
        unique_togetoer = [('activity', 'author')]


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
        to='User',
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
            EntityModel):
    embed_link = models.URLField(
        verbose_name='嵌入链接',
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


class StarMission(EntityModel):
    # TODO: 实现规则的数据化
    class Meta:
        verbose_name = '星光任务'
        verbose_name_plural = '星光任务'
        db_table = 'core_star_mission'


class StarMissionAchievement(UserOwnedModel):
    mission = models.ForeignKey(
        verbose_name='任务',
        to='StarMission',
        related_name='achievements',
    )

    # TODO: 领取之后的关联流水

    class Meta:
        verbose_name = '星光任务成果'
        verbose_name_plural = '星光任务成果'
        db_table = 'core_star_mission_achievement'


class CreditStarTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '星星流水',
        verbose_name_plural = '星星流水',
        db_table = 'core_credit_star_transaction'


class CreditStarIndexTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '星光指数流水',
        verbose_name_plural = '星光指数流水',
        db_table = 'core_credit_star_index_transaction'


class CreditDiamondTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '钻石流水',
        verbose_name_plural = '钻石流水',
        db_table = 'core_credit_diamond_transaction'


class CreditCoinTransaction(AbstractTransactionModel):
    class Meta:
        verbose_name = '金币流水',
        verbose_name_plural = '金币流水',
        db_table = 'core_credit_coin_transaction'


class LevelOption(models.Model):
    class Meta:
        verbose_name = '等级设定',
        verbose_name_plural = '等级设定',
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
        to='ImageModel',
        related_name='informs',
        blank=True,
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
