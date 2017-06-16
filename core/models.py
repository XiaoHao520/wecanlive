from django_base.models import *
from django_member.models import *


# TODO: 充值和提现尚未实现


class Member(AbstractMember,
             UserMarkableModel):
    """ 会员
    注意：用户的追踪状态通过 UserMark 的 subject=follow 类型实现
    """

    class Meta:
        verbose_name = '会员'
        verbose_name_plural = '会员'
        db_table = 'core_member'


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
        db_table = 'core_family_mission_achievement'


class LiveCategory(EntityModel):
    class Meta:
        verbose_name = '直播分类'
        verbose_name_plural = '直播分类'
        db_table = 'core_live_category'



