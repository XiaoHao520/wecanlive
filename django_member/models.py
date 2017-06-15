from django_base.models import *


class AbstractMember(TaggedModel,
                     GeoPositionedModel,
                     EntityModel):
    """ 客户类
    """

    GENDER_SECRET = ''
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_CHOICES = (
        (GENDER_SECRET, '保密'),
        (GENDER_MALE, '男'),
        (GENDER_FEMALE, '女'),
    )

    user = models.OneToOneField(
        primary_key=True,
        verbose_name='用户',
        to=User,
        related_name='%(class)s',
    )

    nickname = models.CharField(
        verbose_name='昵称',
        max_length=255,
        blank=True,
        default='',
    )

    nickname_pinyin = models.CharField(
        verbose_name='昵称拼音',
        max_length=255,
        blank=True,
        default='',
    )

    gender = models.CharField(
        verbose_name='性别',
        max_length=1,
        choices=GENDER_CHOICES,
        default=GENDER_SECRET,
        blank=True,
    )

    real_name = models.CharField(
        verbose_name='真实姓名',
        max_length=150,
        blank=True,
        default='',
    )

    mobile = models.CharField(
        verbose_name='手机号码',
        max_length=45,
        unique=True,
    )

    birthday = models.DateField(
        verbose_name='生日',
        null=True,
        blank=True,
    )

    avatar = models.OneToOneField(
        verbose_name='头像',
        to=ImageModel,
        related_name='customer',
        null=True,
        blank=True,
    )

    search_history = models.TextField(
        verbose_name='搜索历史',
        null=True,
        blank=True,
        help_text='最近10次搜索历史，逗号分隔'
    )

    signature = models.TextField(
        verbose_name='个性签名',
        null=True,
        blank=True,
    )

    district = models.ForeignKey(
        verbose_name='所在地区',
        to='AddressDistrict',
        null=True,
        blank=True,
    )

    address = models.TextField(
        verbose_name='详细地址',
        blank=True,
        default='',
    )

    session_key = models.CharField(
        verbose_name='session_key',
        max_length=255,
        blank=True,
        default='',
        help_text='用于区分单用例登录',
    )

    CONSTELLATION_ARIES = 'ARIES'
    CONSTELLATION_TAURUS = 'TAURUS'
    CONSTELLATION_GEMINI = 'GEMINI'
    CONSTELLATION_CANCER = 'CANCER'
    CONSTELLATION_LEO = 'LEO'
    CONSTELLATION_VIRGO = 'VIRGO'
    CONSTELLATION_LIBRA = 'LIBRA'
    CONSTELLATION_SCORPIO = 'SCORPIO'
    CONSTELLATION_SAGITTARIUS = 'SAGITTARIUS'
    CONSTELLATION_CAPRICORN = 'CAPRICORN'
    CONSTELLATION_AQUARIUS = 'AQUARIUS'
    CONSTELLATION_PISCES = 'PISCES'

    CONSTELLATION_CHOICES = (
        (CONSTELLATION_ARIES, '白羊座'),
        (CONSTELLATION_TAURUS, '金牛座'),
        (CONSTELLATION_GEMINI, '双子座'),
        (CONSTELLATION_CANCER, '巨蟹座'),
        (CONSTELLATION_LEO, '狮子座'),
        (CONSTELLATION_VIRGO, '处女座'),
        (CONSTELLATION_LIBRA, '天秤座'),
        (CONSTELLATION_SCORPIO, '天蝎座'),
        (CONSTELLATION_SAGITTARIUS, '射手座'),
        (CONSTELLATION_CAPRICORN, '摩羯座'),
        (CONSTELLATION_AQUARIUS, '水瓶座'),
        (CONSTELLATION_PISCES, '双鱼座'),
    )

    constellation = models.CharField(
        verbose_name='星座',
        max_length=45,
        choices=CONSTELLATION_CHOICES,
        blank=True,
        default='',
    )

    class Meta:
        abstract = True

    def __str__(self):
        return '{}:{}'.format(self.mobile, self.nickname)

    def save(self, *args, **kwargs):
        # 生成昵称的拼音
        from uuslug import slugify
        self.nickname_pinyin = slugify(self.nickname)
        super().save()
        # 将用户名和 is_active 同步到 User
        # self.user.username = self.mobile
        self.user.is_active = self.is_active
        self.user.save()


class MemberAddress(UserOwnedModel,
                    EntityModel):
    """ 会员地址，可以用于收货地址等用途
    """
    district = models.ForeignKey(
        verbose_name='地区',
        to='AddressDistrict',
        on_delete=models.PROTECT,
        related_name='customer_addresses',
    )

    content = models.CharField(
        verbose_name='详细地址',
        max_length=255,
    )

    receiver = models.CharField(
        verbose_name='收件人',
        max_length=50,
    )

    mobile = models.CharField(
        verbose_name='联系电话',
        max_length=20,
    )

    is_default = models.BooleanField(
        verbose_name='是否默认',
        default=False,
    )

    class Meta:
        verbose_name = '地址'
        verbose_name_plural = '地址'
        db_table = 'member_address'


class OAuthEntry(UserOwnedModel):
    PLATFORM_WECHAT_APP = 'WECHAT_APP'
    PLATFORM_WECHAT_BIZ = 'WECHAT_BIZ'
    PLATFORM_ALIPAY = 'ALIPAY'
    PLATFORM_QQ = 'QQ'
    PLATFORM_WEIBO = 'WEIBO'
    PLATFORM_CHOICES = (
        (PLATFORM_WECHAT_APP, '微信APP'),
        (PLATFORM_WECHAT_BIZ, '微信公众平台'),
        (PLATFORM_ALIPAY, '支付宝'),
        (PLATFORM_QQ, 'QQ'),
        (PLATFORM_WEIBO, '微博'),
    )

    platform = models.CharField(
        verbose_name='第三方平台',
        max_length=20,
        choices=PLATFORM_CHOICES,
        default='',
        blank=True,
    )

    app = models.CharField(
        verbose_name='app',
        max_length=120,
        blank=True,
        default='',
    )

    openid = models.CharField(
        verbose_name='用户OpenID',
        max_length=255,
    )

    nickname = models.CharField(
        verbose_name='用户昵称',
        max_length=128,
        null=True,
    )

    headimgurl = models.URLField(
        verbose_name='用户头像',
        blank=True,
        null=True,
    )

    avatar = models.ImageField(
        verbose_name='头像文件',
        upload_to='oauth/avatar/',
        blank=True,
        null=True,
    )

    params = models.TextField(
        verbose_name='params',
        blank=True,
        default=''
    )

    class Meta:
        verbose_name = '第三方授权'
        verbose_name_plural = '第三方授权'
        db_table = 'member_oauth_entry'
        unique_together = [['app', 'openid']]
