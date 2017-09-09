import json
import re
import os
import os.path
import random

from datetime import datetime, timedelta

from django.db import models
from django.conf import settings
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from . import utils as u
from .middleware import get_request


def patch_methods(model_class):
    def do_patch(cls):
        for k in cls.__dict__:
            obj = getattr(cls, k)
            if not k.startswith('_') and callable(obj):
                setattr(model_class, k, obj)

    return do_patch


class DeletableManager(models.Manager):
    def get_queryset(self):
        if settings.PSEUDO_DELETION:
            return super(DeletableManager, self).get_queryset().filter(is_del=False)
        return super(DeletableManager, self).get_queryset()


class EntityModel(models.Model):
    """ 实体类模型
    加入了一部分的方法：
    * 可删除：这类模型删除的话实际上会隐藏起来，但是不会正式删除数据
    * 时间戳：加入了 date_created 和 date_updated 记录创建和修改的时间
    """

    name = models.CharField(
        verbose_name='名称',
        max_length=255,
        blank=True,
        default='',
    )

    is_del = models.BooleanField(
        verbose_name='已删除',
        default=False,
    )

    is_active = models.BooleanField(
        verbose_name='是否有效',
        default=True,
    )

    is_sticky = models.BooleanField(
        verbose_name='是否置顶',
        default=False,
    )

    sorting = models.SmallIntegerField(
        verbose_name='排序',
        default=0,
        help_text='数字越大越靠前',
    )

    date_created = models.DateTimeField(
        verbose_name='创建时间',
        auto_now_add=True,
    )

    date_updated = models.DateTimeField(
        verbose_name='修改时间',
        auto_now=True,
    )

    objects = DeletableManager()

    default_objects = models.Manager()

    use_for_related_fields = True

    class Meta:
        abstract = True
        ordering = ['-date_created']

    def __str__(self):
        # 如果 name 不填，那么显示内容的前 20 个字符
        return self.name \
               or hasattr(self, 'content') and self.content[:20] \
               or str(self.pk)

    def delete(self, *args, **kwargs):
        """ 接管默认的 Delete 方法，不做真正的删除 """
        if settings.PSEUDO_DELETION:
            self.is_del = True
            self.save()
        else:
            super().delete(*args, **kwargs)

    def destroy(self):
        super().delete()


class HierarchicalModel(models.Model):
    """ 层次模型，具备 parent 和 children 属性
    """
    parent = models.ForeignKey(
        verbose_name='上级',
        to='self',
        related_name='children',
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True


class Tag(models.Model):
    """ 标签
    """

    name = models.CharField(
        verbose_name='名称',
        max_length=255,
    )

    class Meta:
        verbose_name = '标签'
        verbose_name_plural = '标签'
        db_table = 'base_tag'

    def __str__(self):
        return self.name


class TaggedModel(models.Model):
    tags = models.ManyToManyField(
        verbose_name='标签',
        to=Tag,
        related_name='%(class)ss',
        blank=True,
    )

    class Meta:
        abstract = True


class GeoPositionedModel(models.Model):
    """ 包含地理位置的模型
    """

    # 地球半径（米）
    EARTH_RADIUS = 6378245.0

    geo_lng = models.FloatField(
        verbose_name='经度',
        default=0,
        blank=True,
    )

    geo_lat = models.FloatField(
        verbose_name='纬度',
        default=0,
        blank=True,
    )

    radius = models.FloatField(
        verbose_name='半径',
        default=0,
        blank=True,
    )

    geo_label = models.CharField(
        verbose_name='位置标签',
        max_length=255,
        blank=True,
        default='',
    )

    adcode = models.IntegerField(
        verbose_name='行政区划编码',
        default=0,
        help_text='保存时试图自动获取区划编码',
    )

    geo_info = models.TextField(
        verbose_name='地理信息',
        default='',
        blank=True,
        help_text='保存时自动尝试获取地理信息',
    )

    class Meta:
        abstract = True

    # def save(self, *args, **kwargs):
    #     print('save geo positioned model')
    #     # 自动解析地理位置
    #     if settings.AUTO_GEO_DECODE:
    #         try:
    #             info = self.get_geo_decode()
    #             self.geo_info = json.dumps(info)
    #             self.adcode = info.get('addressComponent').get('adcode')
    #         except:
    #             pass
    #     super().save(self, *args, **kwargs)

    @staticmethod
    def inside_china(lat, lng):
        """ 粗算坐标是否在国内
        :param lat:
        :param lng:
        :return:
        """
        return 73.66 < lng < 135.05 and 3.86 < lat < 53.55

    @staticmethod
    def latlng_baidu2qq(lat, lng):
        """ 百度地图坐标转换成QQ地图坐标
        :param lat:
        :param lng:
        :return:
        """
        import math
        x_pi = math.pi * 3000.0 / 180.0
        x = lng - 0.0065
        y = lat - 0.006
        z = (x * x + y * y) ** 0.5 - 0.00002 * math.sin(y * x_pi)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
        lng = z * math.cos(theta)
        lat = z * math.sin(theta)
        return lat, lng

    def geo_qq(self):
        """ 获取 qq 坐标系的坐标（纬度latitude，经度longitude）
        :return:
        """
        return self.latlng_baidu2qq(self.geo_lat, self.geo_lng)

    def geo_lat_qq(self):
        """ 返回 QQ 坐标系纬度 """
        return self.geo_qq[0]

    def geo_lng_qq(self):
        """ 返回 QQ 坐标系经度 """
        return self.geo_qq[1]

    @staticmethod
    def geo_decode(lat, lng):
        from sys import stderr
        from urllib.request import urlopen
        from django.conf import settings
        try:
            resp = urlopen(
                'http://api.map.baidu.com/geocoder/v2/'
                '?location={},{}&output=json&ak={}'.format(
                    lat, lng, settings.BMAP_KEY
                )
            )
            return json.loads(resp.read().decode()).get('result')
        except:
            # 反解地理信息失败
            import traceback
            from sys import stderr
            print(traceback.format_exc(), file=stderr)
            return None

    def get_geo_decode(self):
        return self.geo_decode(self.geo_lat, self.geo_lng)

    def get_label(self):
        info = self.get_geo_decode()
        return info and info.get('formatted_address')

    def get_district_number(self):
        info = self.get_geo_decode()
        address = info and info.get('addressComponent')
        return address and address.get('adcode')

    def get_district(self):
        return AddressDistrict.objects.filter(pk=self.get_district_number() or 0).first()

    def get_full_address(self):
        district = self.get_district()
        return district.full_name + self.geo_label

    def get_district_label(self):
        import re
        district = self.get_district()
        return re.sub(
            r'(?:地区|区|自治州|市郊县|盟|市市辖区|市|省|特別行政區|自治州)$',
            '',
            district.name
        ) if district else ''

    def distance(self):
        """ 获取这个对象离当前登录用户的地理距离，单位是公米 """
        request = get_request()
        if not hasattr(request.user, 'customer'):
            return None
        return self.distance_to(request.user.customer)

    def distance_to(self, item):
        """ 获取当前对象到另一个 GeoPositionedModel 对象的距离
        :param item:
        :return:
        """
        return u.earth_distance(
            item.geo_lat,
            item.geo_lng,
            self.geo_lat,
            self.geo_lng
        )

    @staticmethod
    def annotate_distance_from(qs, lat, lng, field_name='distance'):
        """ 将 queryset 附加一个字段名
        :param qs: 原始 queryset
        :param lat: 参考点的纬度坐标
        :param lng: 参考点的经度坐标
        :param field_name: 附加到对象上的距离字段
        :return: 返回按照对指定坐标点距离从近到远排序的 queryset
        """
        return qs.extra(select={field_name: """{R} * acos(
            sin(radians({lat})) * sin(radians(geo_lat)) +
            cos(radians({lat})) * cos(radians(geo_lat)) * cos(radians({lng}-geo_lng))
        )""".format(R=GeoPositionedModel.EARTH_RADIUS, lat=lat, lng=lng)})

    @staticmethod
    def filter_by_distance(qs, lat, lng, distance, exclude=False):
        """ 根据距离筛选 QuerySet
        :param qs: 原始 queryset
        :param lat: 参考点的纬度坐标
        :param lng: 参考点的经度坐标
        :param distance: 基准距离
        :param exclude: 如果是 False（默认），返回距离小于基准距离的集合
        如果为 True，则返回距离大于基准距离的集合
        :return:
        """
        # 社区公告计算筛选范围
        return qs.extra(where=[
            """{R} * acos(
                sin(radians({lat})) * sin(radians(geo_lat)) +
                cos(radians({lat})) * cos(radians(geo_lat)) * cos(radians({lng}-geo_lng))
            ) {op} {distance}""".format(
                R=GeoPositionedModel.EARTH_RADIUS,
                lat=lat,
                lng=lng,
                distance=distance,
                op='>' if exclude else '<'
            )
        ])


class Keyword(models.Model):
    """ 关键词
    关键词采集自所有的文本，包括用户搜索的输入、商店的详细信息等等；
    可以给一个统一的接口接受一个文本以更新关键词；
    关键词的统计有一个主题的概念，可以分主题对内容进行统计；
    """

    name = models.CharField(
        verbose_name='名称',
        max_length=255,
    )

    frequency = models.BigIntegerField(
        verbose_name='词频',
        default=0,
    )

    subject = models.CharField(
        verbose_name='主题',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = '关键词'
        verbose_name_plural = '关键词'
        db_table = 'base_keyword'
        # unique_together = [['name', 'subject']]

    @staticmethod
    def collect(text, split=True, subject=''):
        """ 收集一个文本的关键词
        给出一段文本，然后对文本进行分词，将所有的分词结果词累计到 keyword 中。
        :param text: 收集的文本
        :param split: 是否进行分词
        :param subject: 统计的主题
        :return:
        """
        import jieba
        import re
        from collections import Counter
        text = re.sub(
            r'[^\u4E00-\u9FA5A-Za-z0-9_-]',
            ' ',
            text
        )
        words = Counter(jieba.cut(text) if split else [text]).items()
        result = list()
        for word, freq in words:
            if text.strip():
                kw, created = Keyword.objects.get_or_create(name=word, subject=subject)
                kw.frequency += freq
                kw.save()
                result.append(kw)
        return result


class UserOwnedModel(models.Model):
    """ 由用户拥有的模型类
    包含作者字段
    """

    author = models.ForeignKey(
        verbose_name='作者',
        to=User,
        related_name='%(class)ss_owned',
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True


class ImageModel(UserOwnedModel, EntityModel):
    """ 图片对象
    由于需要审批，因此需要单独抽出
    """

    image = models.ImageField(
        verbose_name='图片',
        upload_to='images/'
    )

    is_active = models.BooleanField(
        verbose_name='是否可用',
        default=True,
    )

    class Meta:
        verbose_name = '图片'
        verbose_name_plural = '图片'
        db_table = 'base_image'

    def url(self):
        """ 根据可用状态返回图片的 URL
        如果未审批的话返回替代的图片
        :return:
        """
        return self.image.url if self.is_active \
            else static('django_base/images/image-pending.png')


class GalleryModel(models.Model):
    images = models.ManyToManyField(
        verbose_name='图片',
        to='ImageModel',
        related_name='%(class)ss_attached',
        blank=True,
    )

    class Meta:
        abstract = True


class VideoModel(UserOwnedModel, EntityModel):
    """ 视频对象
    """

    video = models.FileField(
        verbose_name='视频',
        upload_to='video/'
    )

    duration = models.FloatField(
        verbose_name='时长',
        blank=True,
        default=0,
    )

    is_active = models.BooleanField(
        verbose_name='是否可用',
        default=True,
    )

    class Meta:
        verbose_name = '视频'
        verbose_name_plural = '视频'
        db_table = 'base_video'

    def url(self):
        return self.video.url if self.is_active else None


class AudioModel(UserOwnedModel, EntityModel):
    """ 音频对象
    """

    audio = models.FileField(
        verbose_name='音频',
        upload_to='audio/',
        blank=True,
        null=True,
    )

    duration = models.FloatField(
        verbose_name='时长',
        blank=True,
        default=0,
    )

    is_active = models.BooleanField(
        verbose_name='是否可用',
        default=True,
    )

    audio_mp3 = models.FileField(
        verbose_name='音频mp3文件',
        upload_to='audio/mp3/',
        null=True,
        blank=True,
    )

    audio_ogg = models.FileField(
        verbose_name='音频ogg文件',
        upload_to='audio/ogg/',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '音频'
        verbose_name_plural = '音频'
        db_table = 'base_audio'

    def url(self):
        return self.audio.url if self.is_active else None

    @classmethod
    def make_from_uploaded_file(cls, file):
        """
        Creates and return an AudioModel instance.
        Usage:
        <input type="file" name="upload" />
        audio = AudioModel.make_from_uploaded_file(request.FILES['upload'])
        :param file:
        :return:
        """
        audio = cls.objects.create()
        temp_path = os.path.join(
            settings.MEDIA_ROOT,
            'audio',
            '{}.{}'.format(audio.id, file.name.split('.')[-1]),
        )
        if settings.NORMALIZE_AUDIO:
            ogg_path = 'audio/ogg/{}.ogg'.format(audio.id)
            mp3_path = 'audio/mp3/{}.mp3'.format(audio.id)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, os.path.dirname(ogg_path)), exist_ok=True)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, os.path.dirname(mp3_path)), exist_ok=True)
            of = open(temp_path, 'wb')
            of.write(file.read())
            of.close()
            from .libs.audiotranscode import AudioTranscode
            at = AudioTranscode()
            at.transcode(temp_path, os.path.join(settings.MEDIA_ROOT, ogg_path))
            at.transcode(temp_path, os.path.join(settings.MEDIA_ROOT, mp3_path))
            audio.audio_ogg.name = ogg_path
            audio.audio_mp3.name = mp3_path
            from mutagen.mp3 import MP3
            audio.duration = MP3(os.path.join(settings.MEDIA_ROOT, mp3_path)).info.length
        else:
            # TODO: not tested
            raw_path = 'audio/raw/{}'.format(file.name)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, os.path.dirname(raw_path)), exist_ok=True)
            of = open(raw_path, 'wb')
            of.write(file.read())
            of.close()
            audio.audio.name = raw_path

        audio.save()
        return audio


class AbstractMessageModel(models.Model):
    """ 消息
    """
    TYPE_TEXT = 'TEXT'
    TYPE_IMAGE = 'IMAGE'
    TYPE_VIDEO = 'VIDEO'
    TYPE_AUDIO = 'AUDIO'
    TYPE_COMBO = 'COMBO'
    TYPE_OBJECT = 'OBJECT'
    TYPE_PROMPT = 'PROMPT'
    TYPE_CHOICES = (
        (TYPE_TEXT, '文本'),
        (TYPE_IMAGE, '图片'),
        (TYPE_VIDEO, '视频'),
        (TYPE_AUDIO, '音频'),
        (TYPE_COMBO, '混合'),
        (TYPE_OBJECT, '对象'),
        (TYPE_PROMPT, '提示'),
    )

    type = models.CharField(
        verbose_name='消息类型',
        choices=TYPE_CHOICES,
        max_length=20,
        default=TYPE_TEXT,
    )

    content = models.TextField(
        verbose_name='内容',
        blank=True,
        default='',
    )

    images = models.ManyToManyField(
        verbose_name='图片',
        to=ImageModel,
        related_name='%(class)ss',
        blank=True,
    )

    videos = models.ManyToManyField(
        verbose_name='视频',
        to=VideoModel,
        related_name='%(class)ss',
        blank=True,
    )

    audios = models.ManyToManyField(
        verbose_name='音频',
        to=AudioModel,
        related_name='%(class)ss',
        blank=True,
    )

    params = models.TextField(
        verbose_name='参数',
        blank=True,
        default='',
        help_text='用 json 存放一些动态的参数',
    )

    class Meta:
        abstract = True


class Comment(HierarchicalModel,
              UserOwnedModel,
              EntityModel,
              AbstractMessageModel):
    content = models.TextField(
        verbose_name='内容',
    )

    class Meta:
        verbose_name = '评论'
        verbose_name_plural = '评论'
        db_table = 'base_comment'

    def delete(self, *args, **kwargs):
        from django_base.middleware import get_request
        user = get_request().user
        if user.is_staff:
            AdminLog.make(
                user,
                AdminLog.TYPE_DELETE,
                self,
                '刪除评论',
            )
        super().delete(*args, **kwargs)

    def get_activeevent_img(self):
        if self.activeevents.first():
            return self.activeevents.first().images.first().image.url
        else:
            return False


class CommentableModel(models.Model):
    comments = models.ManyToManyField(
        verbose_name='评论',
        to=Comment,
        related_name='%(class)ss',
        blank=True,
    )

    class Meta:
        abstract = True


class Rating(UserOwnedModel,
             EntityModel):
    taxonomy = models.CharField(
        verbose_name='分类',
        max_length=50,
        blank=True,
        default='',
    )

    score = models.FloatField(
        verbose_name='评分',
    )

    class Meta:
        verbose_name = '评分'
        verbose_name_plural = '评分'
        db_table = 'base_rating'


class RatableModel(models.Model):
    ratings = models.ManyToManyField(
        verbose_name='评分',
        to='Rating',
        related_name='%(class)ss',
        blank=True,
    )

    class Meta:
        abstract = True


class Message(AbstractMessageModel,
              EntityModel):
    subject = models.CharField(
        verbose_name='主题分类',
        max_length=20,
        blank=True,
        default='',
    )

    broadcast = models.ForeignKey(
        verbose_name='推送',
        to='Broadcast',
        related_name='messages',
        null=True,
        blank=True,
    )

    sender = models.ForeignKey(
        verbose_name='发送用户',
        to=User,
        related_name='messages_sent',
        null=True,
        blank=True,
    )

    receiver = models.ForeignKey(
        verbose_name='接收用户',
        to=User,
        related_name='messages_received',
        null=True,
        blank=True,
    )

    is_read = models.BooleanField(
        verbose_name='是否已读',
        default=False,
    )

    class Meta:
        verbose_name = '消息'
        verbose_name_plural = '消息'
        db_table = 'base_message'


class Broadcast(AbstractMessageModel):
    use_sms = models.BooleanField(
        verbose_name='是否推送手机短信',
        default=False,
    )

    use_jpush = models.BooleanField(
        verbose_name='是否推送手机通知',
        default=False,
    )

    use_email = models.BooleanField(
        verbose_name='是否推送电子邮件',
        default=False,
    )

    use_wechat = models.BooleanField(
        verbose_name='是否推送微信公众号模板消息',
        default=False,
    )

    STATUS_DRAFT = 'DRAFT'
    STATUS_DONE = 'DONE'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_DONE, '已发送'),
    )

    status = models.CharField(
        verbose_name='状态',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    TARGET_LIVE = 'TARGET_LIVE'
    TARGET_SYSTEM = 'TARGET_SYSTEM'
    TARGET_SYSTEM_FAMILYS = 'TARGET_SYSTEM_FAMILYS'
    TARGET_SYSTEM_NOT_FAMILYS = 'TARGET_SYSTEM_NOT_FAMILYS'
    TARGET_ACTIVITY = 'TARGET_ACTIVITY'
    TARGET_CHOICES = (
        (TARGET_LIVE, '直播间消息'),
        (TARGET_SYSTEM, '系统消息'),
        (TARGET_ACTIVITY, '活動消息'),
        (TARGET_SYSTEM_FAMILYS, '系統消息（家族成員）'),
        (TARGET_SYSTEM_NOT_FAMILYS, '系統消息（非家族成員）'),
    )

    target = models.CharField(
        verbose_name='目标用户',
        max_length=30,
        choices=TARGET_CHOICES,
        blank=True,
        null=True,
    )

    groups = models.ManyToManyField(
        verbose_name='推送组',
        to=Group,
        blank=True,
        related_name='broadcasts',
    )

    users = models.ManyToManyField(
        verbose_name='推送用户',
        to=User,
        blank=True,
        related_name='broadcasts',
    )

    date_sent = models.DateTimeField(
        verbose_name='推送时间',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = '消息推送'
        verbose_name_plural = '消息推送'
        db_table = 'base_broadcast'

    def get_recipients(self):
        return User.objects.filter(
            models.Q(groups__broadcasts=self) |
            models.Q(broadcasts=self)
        ).distinct()

    def target_text(self):
        """ 推送群体显示的字段 """
        return ', '.join([u.username for u in self.users.all()]) + ', ' + \
               ', '.join([g.name for g in self.groups.all()])

    def send(self):
        """ 执行推送
        :return:
        """
        if self.status == self.STATUS_DONE:
            raise ValidationError('消息已推送，不能重复操作。')

        for user in self.get_recipients():
            self.messages.create(
                receiver=user,
                # name=self.name,
                content=self.content,
                params=self.params,
            )
            # TODO: 特殊发送渠道需要外接触发实现
        self.status = self.STATUS_DONE
        self.date_sent = datetime.now()
        self.save()


class AddressDistrict(HierarchicalModel):
    """ 地区
    """
    id = models.IntegerField(
        verbose_name='区划编码',
        primary_key=True,
    )

    name = models.CharField(
        verbose_name='名称',
        max_length=45,
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '地区'
        verbose_name_plural = '地区'
        db_table = 'base_address_district'

    def full_name(self):
        return self.parent.full_name() + self.name if self.parent else self.name

    def __str__(self):
        return self.name

    @staticmethod
    def get_geo_decode_by_lat_lng(lat, lng):
        from urllib.request import urlopen
        from django.conf import settings
        try:
            resp = urlopen(
                'http://api.map.baidu.com/geocoder/v2/'
                '?location={},{}&output=json&ak={}'.format(lat, lng, settings.BMAP_KEY)
            )
            return json.loads(resp.read().decode()).get('result')
        except:
            import traceback
            from sys import stderr
            print(traceback.format_exc(), file=stderr)
            return None


class AbstractValidationModel(models.Model):
    """ 抽象验证类
    1. 提交一次验证的时候，必须没有非 EXPIRED 的验证信息；
    2. 提交验证之后，创建一条新的 PersonalValidationInfo 信息；
    3. 新提交的验证，状态为 PENDING，记录 date_submitted；
    4. 管理员权限可以进行审批，或者驳回，改变状态并记录 date_response；
    5. 任何阶段，用户可以取消掉现有的验证信息，变成 EXPIRED 并记录时间；
    6. 取消掉唯一一条活动的验证信息之后，可以提交新的验证信息；
    """

    STATUS_DRAFT = 'DRAFT'
    STATUS_PENDING = 'PENDING'
    STATUS_REJECTED = 'REJECTED'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_PENDING, '等待审批'),
        (STATUS_REJECTED, '驳回'),
        (STATUS_SUCCESS, '成功'),
        (STATUS_EXPIRED, '已失效'),
    )

    status = models.CharField(
        verbose_name='验证状态',
        max_length=20,
        choices=STATUS_CHOICES,
    )

    date_submitted = models.DateTimeField(
        verbose_name='提交时间',
        blank=True,
        null=True,
    )

    date_response = models.DateTimeField(
        verbose_name='审批时间',
        blank=True,
        null=True,
    )

    date_expired = models.DateTimeField(
        verbose_name='失效时间',
        blank=True,
        null=True,
    )

    remark = models.CharField(
        verbose_name='审核不通过原因',
        max_length=255,
        blank=True,
        default='',
    )

    class Meta:
        abstract = True


class AbstractTransactionModel(models.Model):
    user_debit = models.ForeignKey(
        verbose_name='借方用户',
        to=User,
        related_name='%(class)ss_debit',
        null=True,
        blank=True,
        help_text='即余额增加的用户',
    )

    user_credit = models.ForeignKey(
        verbose_name='贷方用户',
        to=User,
        related_name='%(class)ss_credit',
        null=True,
        blank=True,
        help_text='即余额减少的用户',

    )

    amount = models.DecimalField(
        verbose_name='金额',
        max_digits=18,
        decimal_places=2,
    )

    remark = models.CharField(
        verbose_name='备注',
        blank=True,
        default='',
        max_length=255,
    )

    class Meta:
        abstract = True


class Release(EntityModel):
    version = models.CharField(
        verbose_name='版本号',
        max_length=20,
        blank=True,
        default='',
        unique=True,
    )

    platform = models.CharField(
        verbose_name='客户端',
        max_length=20,
        blank=True,
        default='',
    )

    url = models.CharField(
        verbose_name='下载地址',
        max_length=255,
        blank=True,
        default='',
    )

    date_release = models.DateTimeField(
        verbose_name='发布时间',
        blank=True,
        null=True,
    )

    description = models.TextField(
        verbose_name='描述',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '发布版本'
        verbose_name_plural = '发布版本'
        db_table = 'base_release'


class GroupInfo(EntityModel):
    group = models.OneToOneField(
        verbose_name='组',
        to=Group,
        related_name='info',
    )

    is_builtin = models.BooleanField(
        verbose_name='是否内置',
        default=False,
    )

    description = models.CharField(
        verbose_name='描述',
        max_length=255,
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '组信息'
        verbose_name_plural = '组信息'
        db_table = 'base_group_info'


class Menu(HierarchicalModel, models.Model):
    seq = models.IntegerField(
        verbose_name='序号',
        blank=True,
        default=0,
    )

    project = models.CharField(
        verbose_name='项目名称',
        max_length=50,
        blank=True,
        default='',
        help_text='如果有多个后台模块，通过这个字段区分',
    )

    groups = models.ManyToManyField(
        verbose_name='组',
        to=Group,
        related_name='menus',
    )

    name = models.CharField(
        verbose_name='菜单名称',
        max_length=100,
        help_text='建议与路由名称同步',
    )

    title = models.CharField(
        verbose_name='菜单标题',
        max_length=150,
    )

    class Meta:
        verbose_name = '菜单'
        verbose_name_plural = '菜单'
        db_table = 'base_menu'
        ordering = ['seq']

    def __str__(self):
        return '%s: %s' % (self.name, self.title)


class Option(models.Model):
    """
    选项

    TODO: 这里需要做一个初始化脚本，执行安装的话能够将预设置的逻辑选项导入系统。
    """

    key = models.CharField(
        verbose_name='选项关键字', max_length=45, unique=True)

    name = models.CharField(
        verbose_name='选项名称', max_length=100, blank=True, default='')

    value = models.CharField(
        verbose_name='选项值', max_length=2250,
        blank=True, default='')

    class Meta:
        verbose_name = '系统选项'
        verbose_name_plural = '系统选项'
        db_table = 'settings_option'

    @classmethod
    def get(cls, key):
        """ 获取选项值
        :param key: 选项的关键字
        :return: 匹配到的选项值，如果没有此选项，返回 None
        """
        opt = cls.objects.filter(key=key).first()
        return opt and opt.value

    @classmethod
    def unset(cls, key):
        """ 删除选项值
        :param key: 选项的关键字
        :return: 没有返回值
        """
        cls.objects.filter(key=key).delete()

    @classmethod
    def set(cls, key, val):
        """ 设置选项值
        :param key: 选项的关键字
        :param val: 需要设置的目标值
        :return: 没有返回值
        """
        if val is None:
            cls.unset(key)
        opt = cls.objects.filter(key=key).first() or \
              cls.objects.create(key=key, value='')
        opt.value = val or ''
        opt.save()

    def __str__(self):
        return '{}: {}'.format(self.key, self.value)


class Contact(UserOwnedModel):
    """
    联系人
    """
    user = models.ForeignKey(
        verbose_name='目标用户',
        to=User,
        related_name='contacts_related',
    )

    message = models.CharField(
        verbose_name='附带信息',
        max_length=255,
        blank=True,
        default='',
    )

    TYPE_OPEN = 'OPEN'  # 接受对方为联系人
    TYPE_SILENT = 'SILENT'  # 接受对方为联系人，但不提示消息
    TYPE_BLACKLISTED = 'BLACKLISTED'  # 将对方加入黑名单
    TYPE_CHOICES = (
        (TYPE_OPEN, '开放'),
        (TYPE_SILENT, '不提示信息'),
        (TYPE_BLACKLISTED, '黑名单'),
    )

    type = models.CharField(
        verbose_name='联系人状态',
        max_length=20,
        choices=TYPE_CHOICES,
    )

    timestamp = models.DateTimeField(
        verbose_name='时间',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = '联系人'
        verbose_name_plural = '联系人'
        db_table = 'base_contact'
        unique_together = [['author', 'user']]

    @staticmethod
    def apply(user_from, user_to, message='', action=TYPE_OPEN):
        """ 申请添加为联系人或者同意添加对方为联系人
        :param user_from:
        :param user_to:
        :param message: 附带信息
        :param action: OPEN: 添加对方为联系人或者同意添加，SILENT: 拒绝添加，BLACKLISTED: 加入黑名单
        :return:
        """
        contact = Contact.objects.filter(author=user_from, user=user_to).first() \
                  or Contact(author=user_from, user=user_to)
        contact.message = message
        contact.type = action
        contact.save()
        return contact


class ContactSetting(models.Model):
    contact = models.ForeignKey(
        verbose_name='联系人',
        to='Contact',
        related_name='settings',
    )

    key = models.CharField(
        verbose_name='选项名称',
        max_length=100,
    )

    value = models.TextField(
        verbose_name='选项值',
        blank=True,
        default='',
    )

    class Meta:
        verbose_name = '联系人设置'
        verbose_name_plural = '联系人设置'
        db_table = 'base_contact_setting'
        unique_together = [('contact', 'key')]


class UserMark(UserOwnedModel):
    """ 用于让用户对某类对象产生标记的
    例如：用户收藏商品
    UserMark.objects.create(author=user, object=goods, subject='collect')
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey('content_type', 'object_id')

    date_created = models.DateTimeField(
        verbose_name='记录时间',
        auto_now_add=True,
    )

    subject = models.CharField(
        verbose_name='标记类型',
        max_length=20,
    )

    class Meta:
        verbose_name = '用户标记'
        verbose_name_plural = '用户标记'
        db_table = 'base_user_mark'
        unique_together = [['author', 'content_type', 'object_id', 'subject']]

    def __str__(self):
        return '{} - Content type:{}- id:{} - 类型:{}'.format(self.author, self.content_type, self.object_id,
                                                            self.subject)

    def get_activeevent_img(self):
        if self.content_type == ContentType.objects.get(model='activeevent'):
            from core.models import ActiveEvent
            activeevent = ActiveEvent.objects.get(pk=self.object_id)
            if activeevent.images.exists():
                return activeevent.images.first().image.url
            else:
                return False
        else:
            return False

    def is_following(self):
        return self.author.member.isfollow


class UserMarkableModel(models.Model):
    marks = GenericRelation(UserMark)

    class Meta:
        abstract = True

    def get_users_marked_with(self, subject, model=None):
        model = model or type(self)
        content_type = ContentType.objects.get(
            app_label=model._meta.app_label,
            model=model._meta.model_name,
        )
        return User.objects.filter(
            usermarks_owned__content_type=content_type,
            usermarks_owned__object_id=self.pk,
            usermarks_owned__subject=subject,
        )

    def is_marked_by(self, user, subject, model=None):
        return self.get_users_marked_with(subject, model).filter(id=user.id).exists()

    def set_marked_by(self, user, subject, is_marked=True, model=None):
        model = model or type(self)
        content_type = ContentType.objects.get(
            app_label=model._meta.app_label,
            model=model._meta.model_name,
        )
        fields = dict(
            author=user,
            content_type=content_type,
            object_id=self.pk,
            subject=subject,
        )
        print(fields)
        print(model)
        print(self)
        mark = UserMark.objects.filter(**fields).first()
        if is_marked:
            if not mark:
                UserMark.objects.create(**fields)
        else:
            mark.delete()

    @classmethod
    def get_objects_marked_by(cls, user, subject):
        content_type = ContentType.objects.get(
            app_label=cls._meta.app_label,
            model=cls._meta.model_name,
        )
        col = cls._meta.pk.db_column or cls._meta.pk.name + '_id' \
            if type(cls._meta.pk) == models.OneToOneField else cls._meta.pk.name
        qs = cls.objects.extra(
            where=["""
            exists(
                select *
                from base_user_mark um, auth_user u
                where um.subject = '{subject}'
                  and um.author_id = {author_id}
                  and um.object_id = {table}.{col}
                  and um.content_type_id = {content_type_id}
            )
            """.format(subject=subject, author_id=user.id, table=cls._meta.db_table,
                       col=col, content_type_id=content_type.id)]
        )
        return qs


class UserPreferenceField(models.Model):
    key = models.CharField(
        max_length=128,
        verbose_name='选项关键字',
    )

    label = models.CharField(
        max_length=255,
        verbose_name='选项标签',
    )

    CONTROL_TEXT = 'TEXT'
    CONTROL_TEXTAREA = 'TEXTAREA'
    CONTROL_RICHTEXT = 'RICHTEXT'
    CONTROL_DIGIT = 'DIGIT'
    CONTROL_NUMBER = 'NUMBER'
    CONTROL_PERCENT = 'PERCENT'
    CONTROL_CURRENCY = 'CURRENCY'
    CONTROL_IMAGE = 'IMAGE'
    CONTROL_FILE = 'FILE'
    CONTROL_CHECKBOX = 'CHECKBOX'
    CONTROL_RADIOBOX = 'RADIOBOX'
    CONTROL_SELECT = 'SELECT'
    CONTROL_CHOICES = (
        (CONTROL_TEXT, '单行文本'),
        (CONTROL_TEXTAREA, '多行文本'),
        (CONTROL_RICHTEXT, '富文本编辑'),
        (CONTROL_DIGIT, '数字（整数）'),
        (CONTROL_NUMBER, '数字（小数）'),
        (CONTROL_PERCENT, '百分比'),
        (CONTROL_CURRENCY, '货币'),
        (CONTROL_IMAGE, '图片'),
        (CONTROL_FILE, '文件'),
        (CONTROL_CHECKBOX, '多选按钮'),
        (CONTROL_RADIOBOX, '单选按钮'),
        (CONTROL_SELECT, '下拉选项'),
    )

    control = models.CharField(
        verbose_name='控件类型',
        max_length=20,
        choices=CONTROL_CHOICES,
        default=CONTROL_TEXT,
    )

    help_text = models.TextField(
        verbose_name='字段说明',
    )

    default = models.TextField(
        verbose_name='默认值',
    )

    # TODO: 规格待定
    meta = models.TextField(
        verbose_name='元数据',
        help_text='用于存储可用选项等信息',
    )

    class Meta:
        verbose_name = '用户首选项字段'


class UserPreference(models.Model):
    """ 用户首选项
    """

    user = models.ForeignKey(
        verbose_name='用户',
        to=User,
        related_name='preferences',
    )

    key = models.CharField(
        verbose_name='选项名',
        max_length=128,
    )

    value = models.TextField(
        verbose_name='选项值',
        blank=True,
        default='',
    )

    date_updated = models.DateTimeField(
        verbose_name='设置时间',
        blank=True,
        null=True,
        auto_now=True,
    )

    class Meta:
        verbose_name = '用户首选项'
        verbose_name_plural = '用户首选项'
        unique_together = [('user', 'key')]
        db_table = 'base_user_preference'

    @staticmethod
    def get_user_preferences(user):
        return dict([(item.key, item.value) for item in user.preferences.all()])

    @staticmethod
    def hash_payment_password(password):
        from hashlib import sha1
        hasher = sha1(password.encode())
        return hasher.hexdigest()

    @staticmethod
    def payment_password_authenticate(user, password):
        preference = user.preferences.filter(key='payment_password').first()
        if preference and preference.value != UserPreference.hash_payment_password(password):
            return False
        return True

    @staticmethod
    def set(user, key, value):
        pref, created = user.preferences.get_or_create(key=key)
        pref.value = value
        pref.set_time = datetime.now()
        pref.save()


class PlannedTask(models.Model):
    method = models.CharField(
        verbose_name='任务',
        max_length=100,
    )

    args = models.TextField(
        verbose_name='参数',
        blank=True,
        default='',
        help_text='JSON 表示的参数列表',
    )

    kwargs = models.TextField(
        verbose_name='字典参数',
        blank=True,
        default='',
        help_text='JSON 表示的参数字典',
    )

    date_planned = models.DateTimeField(
        verbose_name='计划时间'
    )

    date_execute = models.DateTimeField(
        verbose_name='执行时间',
        blank=True,
        null=True,
    )

    traceback = models.TextField(
        verbose_name='错误信息',
        blank=True,
        default='',
    )

    STATUS_PLANNED = 'PLANNED'
    STATUS_DONE = 'DONE'
    STATUS_FAIL = 'FAIL'
    STATUS_CHOICES = (
        (STATUS_PLANNED, '计划中'),
        (STATUS_DONE, '执行成功'),
        (STATUS_FAIL, '失败'),
    )

    status = models.CharField(
        verbose_name='状态',
        max_length=20,
        default=STATUS_PLANNED,
    )

    class Meta:
        verbose_name = '计划任务'
        verbose_name_plural = '计划任务'
        db_table = 'base_cron_planned_task'

    @staticmethod
    def make(method, date_planned, *args, **kwargs):
        PlannedTask.objects.create(
            method=method,
            date_planned=date_planned,
            args=json.dumps(args),
            kwargs=json.dumps(kwargs),
        )

    @staticmethod
    def trigger_all():
        tasks = PlannedTask.objects.filter(
            status=PlannedTask.STATUS_PLANNED,
            date_planned__lte=datetime.now(),
        )
        for task in tasks:
            task.exec()

    def exec(self):
        if self.status == self.STATUS_DONE or self.date_planned > datetime.now():
            return False
        try:
            args = json.loads(self.args or '[]')
            kwargs = json.loads(self.kwargs or '{}')
            method = getattr(self, self.method)
            method(*args, **kwargs)
            self.status = self.STATUS_DONE
        except Exception as e:
            import traceback
            self.status = self.STATUS_FAIL
            self.traceback = traceback.format_exc()
        self.date_execute = datetime.now()
        self.save()

    # 具体注册的方法
    # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓

    @staticmethod
    def update_user_payment_password(user_id, hashed_password):
        """ 更新用户的支付密码
        :param user_id: 对应的用户
        :param hashed_password: 加密的密码
        :return:
        """
        UserPreference.set(User.objects.get(id=user_id), 'payment_password', hashed_password)

    # 更新每个用户的排行榜
    @staticmethod
    def update_rank_record():
        from core.models import Member, RankRecord
        for member in Member.objects.all():
            rank_records = RankRecord.objects.filter(author=member.user)
            if not rank_records:
                RankRecord.make(member)
            for rank_record in rank_records:
                rank_record.update()

    @staticmethod
    def update_member_check_history():
        from core.models import Member
        for member in Member.objects.all():
            member.check_member_history = None
            member.save()

    @staticmethod
    def settle_activity():
        from core.models import Activity
        for activity in Activity.objects.filter(
            is_settle=False,
        ).all():
            activity.settle()

    @staticmethod
    def change_vip_level(member_id_list):
        # 把vip等级降1，并更新下次降级时间
        from core.models import Member
        member = Member.objects.get(id=member_id_list[0])
        pre_vip_level = member.vip_level
        member.vip_level = pre_vip_level - 1
        if pre_vip_level - 1 >= 0:
            member.date_update_vip = datetime.now()
        else:
            member.date_update_vip = None
        member.save()
        planned_task = PlannedTask.objects.filter(
            method='change_vip_level',
            args__exact=json.dumps([member_id_list[0]]),
        ).first()
        # 降为等级0，依然可以有一个月以续费价升vip1的权利
        if planned_task and pre_vip_level - 1 > 0:
            planned_task.date_planned = planned_task.date_planned + timedelta(days=30)
            planned_task.status = PlannedTask.STATUS_PLANNED
            planned_task.save()
        # 如果降到没有vip等级，切超过一个月，则删除计划任务
        else:
            planned_task.delete()


class AdminLog(UserOwnedModel):
    date_created = models.DateTimeField(
        verbose_name='记录时间',
        auto_now_add=True,
    )

    # LEVEL_DEBUG = 0
    # LEVEL_INFO = 1
    # LEVEL_WARN = 2
    # LEVEL_ERROR = 3
    # LEVEL_FATAL = 4
    # LEVEL_CHOICES = (
    #     (LEVEL_DEBUG, '调试'),
    #     (LEVEL_INFO, '信息'),
    #     (LEVEL_WARN, '警告'),
    #     (LEVEL_ERROR, '错误'),
    #     (LEVEL_FATAL, '致命'),
    # )
    #
    # level = models.IntegerField(
    #     verbose_name='日志级别',
    #     choices=LEVEL_CHOICES,
    # )
    TYPE_CREATE = 'CREATE'
    TYPE_UPDATE = 'UPDATE'
    TYPE_DELETE = 'DELETE'
    TYPE_CHOICES = (
        (TYPE_CREATE, '新建'),
        (TYPE_UPDATE, '修改'),
        (TYPE_DELETE, '刪除'),
    )

    type = models.CharField(
        verbose_name='修改类型',
        choices=TYPE_CHOICES,
        max_length=20,
    )

    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_type', 'target_id')

    content = models.TextField(
        verbose_name='日志内容',
        help_text='JSON格式的日志数据内容，具体使用可以根据应用实际情况而定'
    )

    class Meta:
        verbose_name = '管理日志'
        verbose_name_plural = '管理日志'
        db_table = 'base_admin_log'

    @staticmethod
    def make(author, modification_type, item, content):
        model = type(item)
        content_type = ContentType.objects.get(
            app_label=model._meta.app_label,
            model=model._meta.model_name,
        )
        return AdminLog.objects.create(
            author=author,
            type=modification_type,
            target_type=content_type,
            target_id=item.pk,
            content=content,
        )
