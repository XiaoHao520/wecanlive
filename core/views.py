import re
import json
import random
from time import time
from datetime import datetime, timedelta

from django.shortcuts import render
from django.http import HttpResponse
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

from rest_framework import viewsets
from rest_framework.decorators import list_route, detail_route
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
# import rest_framework_filters as filters
import django_filters as filters
from django_filters import filters, FilterSet

from . import models as m
from . import serializers as s
from . import utils as u
from . import permissions as p
from .utils import response_success, response_fail


def interceptor_get_queryset_kw_field(self):
    """
    用于增强查找类型 query_params 的 get_queryset 中间件方法
    使用方法：
    在 ViewSet 的 get_queryset 函数中：
    def get_queryset(self):
        # 加入这个之后，所有 kw_<field> 格式的 querystring 参数都会
        # 加入到条件中的 qs.filter(field__contains=<value>)
        qs = interceptor_get_queryset_kw_field(self)
        # ... 其他筛选条件
        return qs
    :param self:
    :return:
    """
    qs = super(type(self), self).get_queryset()
    for key in self.request.query_params:
        if key.startswith('kw_'):
            field = key[3:]
            qs = qs.filter(**{
                field + '__contains': self.request.query_params[key]
            })
        elif key.startswith('date_from__'):
            field = key[11:]
            qs = qs.filter(**{
                field + '__date__gte': self.request.query_params[key]
            })
        elif key.startswith('exact__'):
            field = key[7:]
            qs = qs.filter(**{
                field: self.request.query_params[key]
            })
        elif key.startswith('date_to__'):
            field = key[9:]
            qs = qs.filter(**{
                field + '__date__lte': self.request.query_params[key]
            })
    return qs


class GroupViewSet(viewsets.ModelViewSet):
    queryset = m.Group.objects.all()
    serializer_class = s.GroupSerializer
    filter_fields = '__all__'


class GroupInfoViewSet(viewsets.ModelViewSet):
    queryset = m.GroupInfo.objects.all()
    serializer_class = s.GroupInfoSerializer
    filter_fields = '__all__'


class AddressDistrictViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.AddressDistrict.objects.all()
    serializer_class = s.AddressDistrictSerializer


class BankViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Bank.objects.all()
    serializer_class = s.BankSerializer


class ImageViewSet(viewsets.ModelViewSet):
    queryset = m.ImageModel.objects.all()
    serializer_class = s.ImageSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        qs = self.queryset

        # 按 id 筛选
        kw_id = self.request.query_params.get('kw_id')
        if kw_id:
            return self.queryset.model.objects.filter(id=kw_id)

        return qs


class AudioViewSet(viewsets.ModelViewSet):
    queryset = m.AudioModel.objects.all()
    serializer_class = s.AudioSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class UserViewSet(viewsets.ModelViewSet):
    """ User
    """

    class Filter(FilterSet):
        # is_member = filters.BooleanFilter(name='member', lookup_expr='isnull', exclude=True)
        # is_assistant = filters.BooleanFilter(name='assistant', lookup_expr='isnull', exclude=True)

        # is_realty_owner = filters.BooleanFilter('is_realty_agent')

        class Meta:
            model = m.User
            fields = '__all__'

    queryset = m.User.objects.all()
    serializer_class = s.UserSerializer
    filter_class = Filter
    search_fields = (
        'username', 'first_name', 'last_name', 'member__realname')

    def perform_create(self, serializer):
        from django.contrib.auth.hashers import make_password
        serializer.save(
            password=make_password(
                serializer.validated_data.get('password') or ''))

    def perform_update(self, serializer):
        # 锁定用户名就是手机号
        user = self.get_object()
        if hasattr(user, 'member'):
            serializer.save(username=user.member.mobile)
        else:
            serializer.save()

    @detail_route(methods=['GET'])
    def detail(self, request, pk):
        return Response(data=s.UserDetailedSerializer(m.User.objects.get(pk=pk)).data)

    @list_route(methods=['POST'])
    def login_by_openid(self, request):

        from django.contrib.auth import login

        wx_open_id = request.data.get('wxOpenId')
        user = m.User.objects.filter(member__wx_open_id=wx_open_id).first()

        if not user:
            return response_fail('请手动登录')

        login(request, user)

        return Response(
            data=s.UserDetailedSerializer(user).data
        )

    @list_route(methods=['POST'])
    def login(self, request):

        from django.contrib.auth import authenticate, login

        username = request.data.get('username')
        password = request.data.get('password')

        # check either username, mobile or email entry
        user = m.User.objects.filter(
            models.Q(username=username) |
            models.Q(email=username)
        ).first()

        if not user:
            return response_fail('用户不存在', 40001)

        if not user.is_active:
            return response_fail('用户已被锁定', 40002)

        # validates the password
        user = authenticate(username=username, password=password)
        if not user:
            return response_fail('用户密码错误', 40003)

        # deal with the "remember me" option
        if request.data.get('remember', '') not in {True, '1'}:
            request.session.set_expiry(0)

        login(request, user)

        return Response(
            data=s.UserDetailedSerializer(user).data
        )

    @list_route(methods=['GET'])
    def current(self, request):
        if request.user.is_anonymous():
            return response_success('尚未登录')
        return Response(
            data=s.UserDetailedSerializer(request.user).data
        )

    @list_route(methods=['GET'])
    def logout(self, request):
        from django.contrib.auth import logout
        logout(request)
        return response_success('您已成功退出登录')

    @list_route(methods=['POST'])
    def change_password(self, request):
        """ 更改自己的密码
        POST: password_old, password_new
        :param request:
        :return:
        """
        from django.contrib.auth import authenticate, login
        user = request.user

        if request.user.is_anonymous():
            return response_fail('尚未登录', 40020)

        # 旧密码可以不提供，但是提供就要校验
        password_old = request.data.get('password_old')
        if password_old is not None and not authenticate(
                username=user.username,
                password=request.data.get('password_old'), ):
            return response_fail('旧密码不正确', 40021)

        # 新密码必须提供
        password_new = request.data.get('password_new')
        if not password_new:
            return response_fail('必须填写新密码', 40021)

        user.set_password(password_new)
        user.save()
        login(request, authenticate(
            username=user.username,
            password=password_new,
        ))

        return response_success('密码修改成功')

    @detail_route(methods=['POST'])
    def update_password(self, request, pk):
        """ 更改指定用户的密码
        :param request:
        :return:
        """
        user = m.User.objects.get(id=pk)
        if len(request.data.get('password', '')) < 6:
            return response_fail('密码至少需要6位')
        if user.is_staff and not request.user.is_superuser:
            return response_fail('只有超级管理员能够修改管理员密码')
        if not request.user.is_staff:
            return response_fail('只有管理员才能修改用户密码')
        user.set_password(request.data.get('password'))
        user.save()
        return response_success('密码修改成功')

    @list_route(methods=['POST'])
    def send_vcode(self, request):

        mobile = request.data.get('mobile', '')

        try:
            vcode = u.request_mobile_vcode(request, mobile)
        except ValidationError as ex:

            return response_fail(ex.message, 40032)

        msg = '验证码已发送成功'
        # 调试方便直接显示验证码
        if settings.SMS_DEBUG:
            msg = vcode
        return response_success(msg)

    @list_route(methods=['GET'])
    def get_chat_list(self, request):
        """ 获取聊天列表
        所有和自己发过消息的人的列表
        附加最近发布过的消息，按照从新到旧的顺序排列
        :return:
        """

        me = request.user
        sql = '''
        select u.*, max(m.date_created) last_date
        from auth_user u, core_base_message m
        where u.id = m.author_id and m.receiver_id = %s
          or u.id = m.receiver_id and m.author_id = %s
        group by u.id
        order by max(m.date_created) desc
        '''

        users = m.User.objects.raw(sql, [me.id, me.id])

        data = []
        for user in users:
            message = m.Message.objects.filter(
                m.models.Q(author=user, receiver=me) |
                m.models.Q(author=me, receiver=user)
            ).order_by('-date_created').first()
            avatar = user.member.avatar
            unread_count = m.Message.objects.filter(
                author=user,
                receiver=me,
                is_read=False,
            ).count()
            data.append(dict(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                message_date=message.date_created.strftime('%Y-%m-%d %H:%M:%S'),
                message_content='[图片]' if message.type == m.Message.TYPE_IMAGE else
                '[商品]' if message.type == m.Message.TYPE_OBJECT else message.content,
                avatar=avatar and avatar.image.url,
                nickname=user.member.nickname,
                unread_count=unread_count,
            ))
        return Response(data=data)

        # users = m.User.filter(
        #     m.models.Q(messages_owned__receiver=me) |
        #     m.models.Q(messages_received__author=me)
        # ).annotate(
        #     last_time_sent=max(
        #         m.models.Max('messages_owned__date_created'),
        #     ),
        #     last_time_received=max(
        #         m.models.Max('messages_received__date_created'),
        #     ),
        #
        #     )
        # )
        #     .order_by('-last_time')

        # users = m.User.objects.all().extra(select={
        #     'last_date': """
        #         select m.content
        #         from core_base_message m
        #         where m.author_id = %s and m.receiver_id = id
        #           or m.receiver_id = %s and m.author_id = id
        #         order by m.date_created desc
        #         limit 1
        #         """
        # }, select_params=(me.id, me.id)) \
        #     .filter(
        #         m.models.Q(messages_owned__receiver=me) |
        #         m.models.Q(messages_received__author=me)) \
        #     .order_by('-last_date')
        #
        # serializer = s.UserSerializer(data=users, many=True)
        # serializer.is_valid()
        # data = serializer.data
        # for row, user in zip(data, users):
        #     message = m.Message.objects.filter(
        #         m.models.Q(author=user, receiver=me) |
        #         m.models.Q(author=me, receiver=user)
        #     ).order_by('-date_created').first()
        #     row['message_date'] = message.date_created
        #     row['message_text'] = message.content
        # return Response(data=data)

    # 前端忘记密码页面
    @list_route(methods=['post'])
    @u.require_mobile_vcode
    def forgot(self, request):
        mobile = request.data.get('mobile', '')

        user = m.User.objects.filter(username=mobile).first()

        # 验证手机号是否已经注册
        if user:
            from django.contrib.auth import login
            user.set_password(request.data.get('password'))
            user.save()
            login(request, user)
            return Response()
        else:
            return response_fail('请输入正确的手机号码', 40033)

    # 换绑手机号验证旧手机号
    @list_route(methods=['post'], permission_classes=[p.IsAuthenticated])
    @u.require_mobile_vcode
    def unbind_mobile(self, request):
        mobile = request.data.get('mobile', '')
        assert mobile == request.user.username, '不能解绑非当前登录手机号'
        request.session['mobile_unbind_before'] = int(time() + 3600)
        return response_success('验证成功')

    @list_route(methods=['post'], permission_classes=[p.IsAuthenticated])
    @u.require_mobile_vcode
    def bind_new_mobile(self, request):
        assert time() < int(request.session.get('mobile_unbind_before')), \
            '尚未验证旧手机号'
        assert hasattr(request.user, 'member'), '非客户用户无法换绑手机号'
        request.user.member.mobile = u.sanitize_mobile(
            request.data.get('mobile', '')
        )
        request.user.member.save()
        from django.contrib.auth import logout
        logout(request)
        return response_success('绑定成功，请重新登录')

    # @list_route(methods=['GET'], permission_classes=[p.IsAuthenticated])
    # def summary(self, request):
    #     user = request.user
    #     return Response(dict(
    #         cart_record_count=user.shoppingcartrecords_owned.count(),
    #         order_pending_count=user.orders_owned.filter(
    #             status=m.Order.STATUS_PENDING).count(),
    #         demand_active_count=user.demands_owned.filter(
    #             is_active=True).count(),
    #         bank_card_count=user.bankaccounts_owned.count(),
    #     ))

    # @list_route(methods=['POST'], permission_classes=[p.IsAuthenticated])
    # def payment_password_update(self, request):
    #     password_old = request.data.get('password_old')
    #     password_new = u.sanitize_password(request.data.get('password_new'))
    #     if not m.UserPreference.payment_password_authenticate(request.user, password_old):
    #         return u.response_fail('旧密码不正确')
    #     m.UserPreference.set(
    #         request.user,
    #         'payment_password',
    #         m.UserPreference.hash_payment_password(password_new),
    #     )
    #     return u.response_success('修改成功')
    #
    # @list_route(methods=['POST'], permission_classes=[p.IsAuthenticated])
    # def payment_password_authenticate(self, request):
    #     password = request.data.get('password')
    #     return u.response_success('验证成功') \
    #         if m.UserPreference.payment_password_authenticate(request.user, password) \
    #         else u.response_fail('验证失败')

    @detail_route(methods=['POST'])
    def read_messages(self, request, pk):
        """ 标记当前用户与指定用户的消息为已读 """
        user = m.User.objects.get(pk=pk)
        user.messages_owned.filter(
            receiver=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response(1)


class MessageViewSet(viewsets.ModelViewSet):
    class Filter(FilterSet):
        # 系统消息
        is_from_system = filters.BooleanFilter(
            name='author',
            lookup_expr='isnull',
        )
        # 客服消息
        is_from_service = filters.BooleanFilter(
            name='author__is_staff',
        )
        last_id = filters.Filter(
            name='id',
            lookup_expr='gt',
        )

        class Meta:
            model = m.Message
            fields = '__all__'

    filter_class = Filter
    queryset = m.Message.objects.all()
    serializer_class = s.MessageSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        qs = super().get_queryset()
        # users_related = self.request.query_params.get('users_related', '0').split(',')
        # print(users_related)
        # if users_related:
        qs = qs.filter(m.models.Q(
            # author__id__in=users_related,
            receiver=self.request.user,
        ) | m.models.Q(
            # receiver__id__in=users_related,
            author=self.request.user,
        ))
        return qs

    @list_route(methods=['POST'])
    def create_message(self, request):
        is_approved = request.data.get('is_approved')
        message_type = request.data.get('message_type')
        object = request.data.get('object')
        if is_approved:
            m.Message.create_message(object, message_type)
        else:
            m.Message.create_message(object, message_type)
        return Response(data=True)


class MenuViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Menu.objects.all()
    serializer_class = s.MenuSerializer

    @list_route(methods=['POST'], permission_classes=[p.IsAdminUser])
    def sync(self, request):
        project = request.data.get('project') or ''
        menus = []
        index = 0
        for menu in request.data.get('menus'):
            index += 1
            link = menu.get('link')
            menu_name = link and link.get('name')
            if not menu_name:
                menu_name = 'menu_{}'.format(index)
            menus.append(dict(
                title=menu.get('title'),
                name=menu_name,
                parent=None,
            ))
            sub_index = 0
            for sub_menu in menu.get('sub_menus'):
                sub_index += 1
                link = sub_menu.get('link')
                sub_menu_name = link and link.get('name')
                if not sub_menu_name:
                    sub_menu_name = 'menu_{}_{}'.format(index, sub_index)
                menus.append(dict(
                    title=sub_menu.get('title'),
                    name=sub_menu_name,
                    parent=menu_name,
                ))
        # 删除多余的菜单
        m.Menu.objects.filter(project=project).exclude(
            name__in=[menu.get('name') for menu in menus],
        ).delete()
        # 逐项更新菜单
        seq = 1
        for item in menus:
            menu = m.Menu.objects.filter(name=item.get('name'),
                                         project=project).first() or m.Menu()
            menu.project = project
            menu.name = item.get('name')
            menu.title = item.get('title')
            menu.parent = m.Menu.objects.filter(
                name=item.get('parent', ''),
                project=project,
            ).first()
            menu.seq = seq
            seq += 1
            menu.save()
        return u.response_success('菜单更新成功')

    @list_route(methods=['GET'], permission_classes=[p.IsAuthenticated])
    def get_user_menu(self, request):
        data = []
        project = request.query_params.get('project') or ''
        if not request.user.is_anonymous():
            for menu in m.Menu.objects.filter(
                    project=project,
                    children__groups__user=request.user,
                    parent=None).distinct():
                data.append(dict(
                    id=menu.id,
                    title=menu.title,
                    expanded=False,
                    sub_menus=[dict(
                        parent=submenu.parent.id,
                        title=submenu.title,
                        link=dict(
                            name=submenu.name,
                        )) for submenu in menu.children.filter(groups__user=request.user)],
                ))
        return Response(data=data)


class BroadcastViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Broadcast.objects.all()
    serializer_class = s.BroadcastSerializer

    def perform_create(self, serializer):
        # 保存的时候自动发送
        broadcast = serializer.save()
        broadcast.send()


class MemberViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Member.objects.all()
    serializer_class = s.MemberSerializer


class RobotViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Robot.objects.all()
    serializer_class = s.RobotSerializer


class CelebrityCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CelebrityCategory.objects.all()
    serializer_class = s.CelebrityCategorySerializer


class CreditStarTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditStarTransaction.objects.all()
    serializer_class = s.CreditStarTransactionSerializer


class CreditStarIndexTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditStarIndexTransaction.objects.all()
    serializer_class = s.CreditStarIndexTransactionSerializer


class CreditDiamondTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditDiamondTransaction.objects.all()
    serializer_class = s.CreditDiamondTransactionSerializer


class CreditCoinTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditCoinTransaction.objects.all()
    serializer_class = s.CreditCoinTransactionSerializer


class BadgeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Badge.objects.all()
    serializer_class = s.BadgeSerializer


class DailyCheckInLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.DailyCheckInLog.objects.all()
    serializer_class = s.DailyCheckInLogSerializer


class FamilyViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Family.objects.all()
    serializer_class = s.FamilySerializer


class FamilyMemberViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMember.objects.all()
    serializer_class = s.FamilyMemberSerializer


class FamilyArticleViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyArticle.objects.all()
    serializer_class = s.FamilyArticleSerializer


class FamilyMissionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMission.objects.all()
    serializer_class = s.FamilyMissionSerializer


class FamilyMissionAchievementViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMissionAchievement.objects.all()
    serializer_class = s.FamilyMissionAchievementSerializer


class LiveCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveCategory.objects.all()
    serializer_class = s.LiveCategorySerializer


class LiveViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Live.objects.all()
    serializer_class = s.LiveSerializer


class LiveBarrageViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveBarrage.objects.all()
    serializer_class = s.LiveBarrageSerializer


class LiveWatchLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveWatchLog.objects.all()
    serializer_class = s.LiveWatchLogSerializer


class ActiveEventViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActiveEvent.objects.all()
    serializer_class = s.ActiveEventSerializer


class PrizeCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeCategory.objects.all()
    serializer_class = s.PrizeCategorySerializer


class PrizeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Prize.objects.all()
    serializer_class = s.PrizeSerializer


class PrizeTransitionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeTransition.objects.all()
    serializer_class = s.PrizeTransitionSerializer


class PrizeOrderViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeOrder.objects.all()
    serializer_class = s.PrizeOrderSerializer


class ExtraPrizeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ExtraPrize.objects.all()
    serializer_class = s.ExtraPrizeSerializer


class StatisticRuleViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StatisticRule.objects.all()
    serializer_class = s.StatisticRuleSerializer


class ActivityViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Activity.objects.all()
    serializer_class = s.ActivitySerializer


class ActivityParticipationViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActivityParticipation.objects.all()
    serializer_class = s.ActivityParticipationSerializer


class NotificationsViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Notifications.objects.all()
    serializer_class = s.NotificationsSerializer


class VisitLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.VisitLog.objects.all()
    serializer_class = s.VisitLogSerializer


class MovieViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Movie.objects.all()
    serializer_class = s.MovieSerializer


class StarBoxViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarBox.objects.all()
    serializer_class = s.StarBoxSerializer


class StarBoxRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarBoxRecord.objects.all()
    serializer_class = s.StarBoxRecordSerializer


class RedBagRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.RedBagRecord.objects.all()
    serializer_class = s.RedBagRecordSerializer


class StarMissionAchievementViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarMissionAchievement.objects.all()
    serializer_class = s.StarMissionAchievementSerializer


class LevelOptionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LevelOption.objects.all()
    serializer_class = s.LevelOptionSerializer


class InformViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Inform.objects.all()
    serializer_class = s.InformSerializer


class FeedbackViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Feedback.objects.all()
    serializer_class = s.FeedbackSerializer


class BannerViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Banner.objects.all()
    serializer_class = s.BannerSerializer


class SensitiveWordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.SensitiveWord.objects.all()
    serializer_class = s.SensitiveWordSerializer


class DiamondExchangeRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.DiamondExchangeRecord.objects.all()
    serializer_class = s.DiamondExchangeRecordSerializer

