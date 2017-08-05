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
        value = self.request.query_params[key]
        if key.startswith('kw_'):
            field = key[3:]
            qs = qs.filter(**{field + '__contains': value})
        elif key.startswith('exact__'):
            field = key[7:]
            qs = qs.filter(**{field: value})
        elif key.startswith('date_from__'):
            field = key[11:]
            qs = qs.filter(**{field + '__date__gte': value})
        elif key.startswith('date_to__'):
            field = key[9:]
            qs = qs.filter(**{field + '__date__lte': value})
        elif key.startswith('ne__'):
            field = key[4:]
            qs = qs.exclude(**{field: value})
        elif re.match(r'^(?:gt|gte|lt|lte|contains)__', key):
            pos = key.find('__')
            op = key[:pos]
            field = key[pos + 2:]
            qs = qs.filter(**{field + '__' + op: value})
    return qs


class GroupViewSet(viewsets.ModelViewSet):
    queryset = m.Group.objects.all()
    serializer_class = s.GroupSerializer
    filter_fields = '__all__'
    ordering = ['-pk']


class GroupInfoViewSet(viewsets.ModelViewSet):
    queryset = m.GroupInfo.objects.all()
    serializer_class = s.GroupInfoSerializer
    filter_fields = '__all__'
    ordering = ['-pk']


class AddressDistrictViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.AddressDistrict.objects.all()
    serializer_class = s.AddressDistrictSerializer
    ordering = ['-pk']


class BankViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Bank.objects.all()
    serializer_class = s.BankSerializer
    ordering = ['-pk']


class ImageViewSet(viewsets.ModelViewSet):
    filter_fields = ['author', 'name', 'is_active', 'id']
    queryset = m.ImageModel.objects.all()
    serializer_class = s.ImageSerializer
    ordering = ['-pk']

    def perform_create(self, serializer):
        serializer.save(author=not self.request.user.is_anonymous and self.request.user or None)

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
    ordering = ['-pk']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


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

    # ordering = ['-pk']

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

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
            sender=self.request.user,
        ))

        family = self.request.query_params.get('family')
        if family:
            qs = qs.filter(families__id=family).order_by('date_created')
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
    ordering = ['-pk']

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
                        )) for submenu in menu.children.filter(groups__user=request.user).distinct()],
                ))
        return Response(data=data)


class BroadcastViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Broadcast.objects.all()
    serializer_class = s.BroadcastSerializer
    ordering = ['-pk']

    def perform_create(self, serializer):
        # 保存的时候自动发送
        broadcast = serializer.save()
        broadcast.send()


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
    ordering = ['-pk']

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

        # if user.is_superuser:
        #     m.AdminLog.make(request.user, request.user,
        #                     '管理员用户【{}】登录了系统'.format(request.user.username))

        login(request, user)

        return Response(
            data=s.UserDetailedSerializer(user).data
        )

    @list_route(methods=['POST'])
    def landing_with_wecan_session(self, request):
        session = request.data.get('session')
        aes = u.AESCipher(settings.WECAN_AES_KEY_SERVER)
        data = aes.decrypt(session)
        account = data.split('|')[1]
        user = m.User.objects.filter(username=account).first() or \
               m.User.objects.create_user(username=account)
        member, created = m.Member.objects.get_or_create(
            user=user,
            defaults=dict(mobile=account),
        )
        # 创建完之后登录之
        from django.contrib.auth import login
        login(request, user)
        data = s.MemberSerializer(member).data
        data['is_register'] = created
        return Response(data=data)

    @list_route(methods=['GET'])
    def current(self, request):
        if request.user.is_anonymous():
            return response_fail('')
        data = s.UserDetailedSerializer(request.user).data
        if hasattr(request.user, 'member'):
            data['tencent_sig'] = request.user.member.tencent_sig
        return Response(data=data)

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
        # assert time() < int(request.session.get('mobile_unbind_before')), \
        #     '尚未验证旧手机号'
        assert not m.Member.objects.filter(mobile=request.data.get('mobile', '')).exists(), \
            '您要變更的手機號碼已經註冊，不能綁定'
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


class MemberViewSet(viewsets.ModelViewSet):
    class Filter(FilterSet):
        is_active = filters.BooleanFilter(
            name='user__is_active',
        )
        is_contact_from = filters.Filter(
            name='user__contacts_related__author',
        )
        is_contact_to = filters.Filter(
            name='user__contacts_owned__author',
        )

        class Meta:
            model = m.Member
            fields = '__all__'

    queryset = m.Member.objects.all()
    serializer_class = s.MemberSerializer
    filter_class = Filter
    search_fields = ['nickname', 'mobile']
    filter_fields = '__all__'

    # def perform_update(self, serializer):
    #     # 级联更新 user 的 username 为手机号
    #     member = self.get_object()
    #     user = member.user
    #     user.username = member.mobile
    #     user.save()
    #     serializer.save()

    def perform_destroy(self, instance):
        deleted_username = 'deleted_' \
                           + datetime.now().strftime('%Y%m%d%H%M%S') \
                           + '_' + instance.user.username
        instance.mobile = deleted_username
        instance.save()
        # 废除用户，但也不是真的删除
        user = instance.user
        user.is_active = False
        user.username = deleted_username
        user.is_staff = False
        user.is_superuser = False
        user.save()
        instance.delete()

    @list_route(methods=['post'])
    @u.require_mobile_vcode
    def register(self, request):

        # 获取参数
        mobile = u.sanitize_mobile(request.data.get('mobile'))
        password = u.sanitize_password(request.data.get('password'))

        # 校验手机号是否已被注册
        user = m.User.objects.filter(
            models.Q(username=mobile)
        ).first()

        if user:
            return response_fail('註冊失敗，手機號碼已被註冊！', 40031)

        # 执行创建
        user = m.User.objects.create_user(
            username=mobile,
            password=password,
        )

        try:
            member = m.Member.objects.create(
                user=user,
                mobile=mobile,
            )
        except ValidationError as ex:
            # 如果在创建客户这一步挂了，要把刚才创建的用户擦掉
            user.delete()
            return response_fail(ex.message, 40032)

        # 创建完之后登录之
        from django.contrib.auth import login
        login(request, user)

        return Response(data=s.MemberSerializer(member).data)

    @detail_route(methods=['POST'])
    def change_mobile(self, request, pk):
        # 获取参数
        try:
            mobile = u.sanitize_mobile(request.data.get('mobile'))
        except ValidationError as ex:
            return response_fail(ex.message, 40030)
        # 校验手机号是否已被注册
        user = m.User.objects.filter(
            models.Q(username=mobile)
        ).first()

        if user:
            return response_fail('换绑失败，该手机号已被注册', 40031)

        member = m.Member.objects.get(pk=pk)
        member.mobile = mobile
        member.save()
        return Response('换绑成功')

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        member_id = self.request.query_params.get('member')
        is_follow = self.request.query_params.get('is_follow')
        is_followed = self.request.query_params.get('is_followed')
        if member_id:
            member = m.Member.objects.filter(user_id=member_id).first()
            if member and is_follow:
                qs = member.get_follow()
            elif member and is_followed:
                qs = member.get_followed()

        invite = self.request.query_params.get('invite')
        if invite:
            qs = qs.filter(user__contacts_owned__user=self.request.user
                           ).exclude(user__contacts_related__author=self.request.user)

        rank_type = self.request.query_params.get('rank_type')

        if rank_type and rank_type == 'rank_diamond':
            qs = m.Member.objects.annotate(
                amount=m.models.Sum(
                    'user__creditdiamondtransactions_debit__prize_orders__diamond_transaction__amount'
                )
            ).order_by('-amount')
        if rank_type and rank_type == 'rank_prize':
            qs = m.Member.objects.annotate(
                amount=m.models.Sum('user__prizeorders_owned__sender_prize_transaction__amount')
            ).order_by('-amount')
        if rank_type and rank_type == 'rank_star':
            # TODO：根据收到主播元气指数排序
            qs = m.Member.objects.annotate(
                amount=m.models.Sum('user__creditstarindexsendertransactions_credit__amount')
                       - m.models.Sum('user__creditstarindexsendertransactions_debit__amount')
            ).order_by('amount')

        is_withdraw_blacklisted = self.request.query_params.get('is_withdraw_blacklisted')
        if is_withdraw_blacklisted == 'true':
            qs = qs.filter(is_withdraw_blacklisted=True)
        elif is_withdraw_blacklisted == 'false':
            qs = qs.exclude(is_withdraw_blacklisted=True)

        return qs

    @list_route(methods=['post'])
    def update_member_info(self, request):
        avatar = request.data.get('avatar')
        nickname = request.data.get('nickname')
        gender = request.data.get('gender')
        age = request.data.get('age')
        constellation = request.data.get('constellation')
        try:
            if avatar:
                avatarObj = m.ImageModel.objects.filter(id=avatar).first()
                request.user.member.avatar = avatarObj
            request.user.member.nickname = nickname
            request.user.member.gender = gender
            request.user.member.age = age
            request.user.member.constellation = constellation
            request.user.member.save()
        except ValidationError as ex:
            return Response(data=False)
        return Response(data=True)

    @detail_route(methods=['POST'])
    def follow(self, request, pk):
        member = m.Member.objects.get(pk=pk)
        # 指定目标状态或者反转当前的状态
        is_follow = request.data.get('is_follow') == '1' if 'is_follow' in request.data \
            else not member.is_followed_by_current_user()
        member.set_followed_by(request.user, is_follow)
        return u.response_success('')

    @detail_route(methods=['GET'])
    def get_contact_list(self, request, pk):
        # 当前用户所有联系人
        member = m.Member.objects.get(pk=pk)

        contact_list = m.Member.objects.filter(m.models.Q(user__contacts_related__author=member.user),
                                               m.models.Q(user__contacts_owned__user=member.user))

        data = []
        for contact in contact_list:
            unread = m.Message.objects.filter(sender=contact.user,
                                              receiver=member.user,
                                              is_read=False).count()
            data.append(dict(
                id=contact.user.id,
                nickname=contact.nickname,
                avatar_url=contact.avatar.image.url,
                unread=unread,
            ))
        return Response(data=data)

    @list_route(methods=['GET'])
    def get_prize_rank(self, request):
        # 个人送礼排行

        members = m.Member.objects.filter(
            m.models.Q(user__prizeorders_owned__diamond_transaction__user_debit=self.request.user) |
            m.models.Q(user__prizeorders_owned__receiver_star_index_transaction__user_debit=self.request.user)
        ).distinct().all()
        rank = []
        for member in members:
            rank_item = dict()
            diamond_amount = m.PrizeOrder.objects.filter(
                author=member.user,
                diamond_transaction__user_debit=self.request.user
            ).aggregate(
                amount=models.Sum('diamond_transaction__amount')
            ).get('amount') or 0

            star_amount = m.PrizeOrder.objects.filter(
                author=member.user,
                receiver_star_index_transaction__user_debit=self.request.user
            ).aggregate(
                amount=models.Sum('receiver_star_index_transaction__amount')
            ).get('amount') or 0
            # todo: 礼物价值按照　元气指数＋钻石数
            amount = diamond_amount + star_amount
            rank_item['amount'] = amount
            rank_item['member'] = s.MemberSerializer(member).data
            rank.append(rank_item)
        # todo: 只要３个
        return Response(data=sorted(rank, key=lambda item: item['amount'], reverse=True))

    @detail_route(methods=['GET'])
    def get_live_prize(self, request, pk):
        user = m.User.objects.get(pk=pk)

        prizes = m.Prize.objects.filter(
            transactions__user_debit=user,
            transactions__user_credit=user,
        ).distinct().all()
        data = []
        for prize in prizes:
            prize_transaction = m.PrizeTransaction.objects.filter(
                user_debit=user,
                user_credit=user,
                prize=prize,
            )
            amount = prize_transaction.all().aggregate(amount=m.models.Sum('amount')).get('amount') or 0

            first_pk = prize_transaction.order_by('pk').first().pk

            item = dict(
                prize=s.PrizeSerializer(prize).data,
                amount=amount,
                first_pk=first_pk,
            )
            data.append(item)
        return Response(data=sorted(data, key=lambda item: item['first_pk'], reverse=True))


class RobotViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Robot.objects.all()
    serializer_class = s.RobotSerializer
    ordering = ['-pk']


class CelebrityCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CelebrityCategory.objects.all()
    serializer_class = s.CelebrityCategorySerializer
    ordering = ['-pk']


class CreditStarTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditStarTransaction.objects.all()
    serializer_class = s.CreditStarTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']


class CreditStarIndexReceiverTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditStarIndexReceiverTransaction.objects.all()
    serializer_class = s.CreditStarIndexReceiverTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']


class CreditStarIndexSenderTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditStarIndexSenderTransaction.objects.all()
    serializer_class = s.CreditStarIndexSenderTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']


class CreditDiamondTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditDiamondTransaction.objects.all()
    serializer_class = s.CreditDiamondTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']

    @list_route(methods=['GET'])
    def get_ranking_list(self, request):
        """
        获取钻石获得数排行榜
        :param request:
        :return:
        """
        # type   0:日榜； 1:周榜； 2：总榜
        type = request.data.get('type')
        data = []
        users = []
        transactions = m.CreditDiamondTransaction.objects.filter(user_debit=request.user)
        for transaction in transactions:
            if not transaction.user_credit in users:
                users.append(transaction.user_credit)
        for user in users:
            amount = m.CreditDiamondTransaction.objects.filter(
                user_debit=request.user,
                user_credit=user).all().aggregate(amount=models.Sum('amount')).get('amount') or 0
        return Response(data=data)


class CreditCoinTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.CreditCoinTransaction.objects.all()
    serializer_class = s.CreditCoinTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class BadgeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Badge.objects.all()
    serializer_class = s.BadgeSerializer

    # ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)

        live_author = self.request.query_params.get('live_author')
        next_diamond_badge = self.request.query_params.get('next_diamond_badge')

        if live_author and next_diamond_badge:
            live_author_diamond_count = m.User.objects.get(pk=live_author).member.diamond_count()
            qs = qs.filter(
                date_from__lt=datetime.now(),
                date_to__gt=datetime.now(),
                badge_item=m.Badge.ITEM_COUNT_RECEIVE_DIAMOND,
                item_value__gt=live_author_diamond_count,
            ).order_by('item_value')

        return qs


class BadgeRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.BadgeRecord.objects.all()
    serializer_class = s.BadgeRecordSerializer

    # ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        live_author = self.request.query_params.get('live_author')
        if live_author:
            qs = qs.extra(
                select=dict(
                    date_active='DATE_ADD(core_badge_record.date_created, INTERVAL core_badge.validity DAY)'
                ),
                where=[
                    'DATE_ADD(core_badge_record.date_created, INTERVAL core_badge.validity DAY)>\'{}\''.format(
                        datetime.now())
                ]
                # active=models.F('date_created')+timedelta(days=badge__validity)
            ).filter(
                # user_debit_id=F('user_credit_id')+F,
                author__id=live_author,
                badge__date_from__lt=datetime.now(),
                badge__date_to__gt=datetime.now(),
                # date_active__gt=datetime.now(),
            )
            # print(qs.query)

        return qs


class DailyCheckInLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.DailyCheckInLog.objects.all()
    serializer_class = s.DailyCheckInLogSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def daily_checkin(self, request):
        today_daily = m.DailyCheckInLog.objects.filter(
            author=self.request.user,
            date_created__date=datetime.now().date(),
        ).exists()
        if today_daily:
            return response_fail('今天已經簽到了')
        daily_check = m.DailyCheckInLog.check_in(self.request.user)
        print(daily_check)
        return Response(data=dict(
            daily_check=s.DailyCheckInLogSerializer(daily_check['daily_check']).data,
            continue_daily_check=s.DailyCheckInLogSerializer(daily_check['continue_daily_check']).data,
        ))


class FamilyViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Family.objects.all()
    serializer_class = s.FamilySerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        return qs

    @list_route(methods=['POST'])
    def create_family(self, request):
        # 创建家族
        family = m.Family.objects.create(
            name=request.data.get('name'),
            family_introduce=request.data.get('family_introduce'),
            author=self.request.user,
            logo=m.ImageModel.objects.get(pk=request.data.get('logo')),
        )
        m.FamilyMember.objects.create(
            family=family,
            author=self.request.user,
            status=m.FamilyMember.STATUS_APPROVED,
            date_approved=datetime.now(),
            role=m.FamilyMember.ROLE_MASTER,
        )
        return Response(data=s.FamilySerializer(family).data)


class FamilyMemberViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMember.objects.all()
    serializer_class = s.FamilyMemberSerializer
    ordering = ['date_approved']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        family_id = self.request.query_params.get('family')
        search = self.request.query_params.get('search')
        if family_id:
            family = m.Family.objects.get(id=family_id)
            qs = qs.filter(
                family=family,
                status=m.FamilyMember.STATUS_APPROVED,
            )
        if search:
            qs = qs.filter(
                author__member__nickname__contains=search,
            )
        return qs

    @list_route(methods=['POST'])
    def family_manage(self, request):
        type = request.data.get('type')
        members = m.FamilyMember.objects.filter(
            id__in=request.data.get('select'),
            family__id=request.data.get('family'),
        ).all()
        for member in members:
            if type == 'manage':
                member.role = m.FamilyMember.ROLE_ADMIN
                member.save()
            if type == 'normal':
                member.role = m.FamilyMember.ROLE_NORMAL
                member.save()
            if type == 'delete':
                member.delete()
            if type == 'ban':
                member.is_ban = True
                member.save()
            if type == 'unban':
                member.is_ban = False
                member.save()
        return Response(data=True)

    @list_route(methods=['POST'])
    def modify_member_title(self, request):
        select = request.data.get('select')
        user = self.request.user
        title = request.data.get('title')
        family = m.Family.objects.get(pk=request.data.get('family'))
        m.FamilyMember.modify_member_title(user, select, title, family)
        return Response(data=True)


class FamilyArticleViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyArticle.objects.all()
    serializer_class = s.FamilyArticleSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        family_id = self.request.query_params.get('family')
        if family_id:
            family = m.Family.objects.get(id=family_id)
            qs = qs.filter(family=family)
        return qs

    @list_route(methods=['POST'])
    def batch_delete(self, request):
        # 批量刪除家族公告
        select = request.data.get('select')
        articles = m.FamilyArticle.objects.filter(
            id__in=select,
        ).all()

        for article in articles:
            article.delete()

        return Response(data=True)


class FamilyMissionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMission.objects.all()
    serializer_class = s.FamilyMissionSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        family_id = self.request.query_params.get('family')
        if family_id:
            family = m.Family.objects.get(id=family_id)
            qs = qs.filter(family=family)
        return qs


class FamilyMissionAchievementViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.FamilyMissionAchievement.objects.all()
    serializer_class = s.FamilyMissionAchievementSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class LiveCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveCategory.objects.all()
    serializer_class = s.LiveCategorySerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class LiveViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Live.objects.all()
    serializer_class = s.LiveSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        member_id = self.request.query_params.get('member')
        live_status = self.request.query_params.get('live_status')
        followed_by = self.request.query_params.get('followed_by')
        up_liveing = self.request.query_params.get('up_liveing')
        down_liveing = self.request.query_params.get('down_liveing')

        if member_id:
            member = m.Member.objects.filter(
                user_id=member_id
            ).first()
            if member:
                qs = qs.filter(author=member.user)

        if live_status and live_status == 'ACTION':
            qs = qs.filter(
                date_end=None,
            )
        elif live_status and live_status == 'OVER':
            qs = qs.exclude(
                date_end=None,
            )
        if followed_by:
            user = m.User.objects.filter(id=followed_by).first()
            users_following = user.member.get_follow()
            users_friend = m.Member.objects.filter(user__contacts_related__author=user)
            qs = qs.filter(
                m.models.Q(author__member__in=users_following) |
                m.models.Q(author__member__in=users_friend)
            )

        if up_liveing:
            qs = qs.filter(
                id__gt=up_liveing,
                date_end=None,
            ).order_by('pk')

        if down_liveing:
            qs = qs.filter(
                id__lt=down_liveing,
                date_end=None,
            ).order_by('-pk')

        return qs

    @detail_route(methods=['POST'])
    def follow(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        # 指定目标状态或者反转当前的状态
        is_follow = request.data.get('is_follow') == '1' if 'is_follow' in request.data \
            else not live.is_followed_by_current_user()
        live.set_followed_by(request.user, is_follow)
        return u.response_success('')

    @detail_route(methods=['POST'])
    def like(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        # 指定目标状态或者反转当前的状态
        is_like = request.data.get('is_like') == '1' if 'is_like' in request.data \
            else not live.is_liked_by_current_user()
        live.set_like_by(request.user, is_like)
        return u.response_success('')

    @detail_route(methods=['PATCH'])
    def add_like_count(self, request, pk):
        """ 后台记录添加记心形的数量 """
        count = int(request.data.get('count', 1))
        m.Live.objects.filter(pk=pk).update(like_count=models.F('like_count') + count)
        return u.response_success()

    @list_route(methods=['POST'])
    def start_live(self, request):
        assert not request.user.is_anonymous, '请先登录'
        name = request.data.get('name')
        password = request.data.get('password')
        paid = request.data.get('paid')
        quota = request.data.get('quota')
        category = m.LiveCategory.objects.get(id=request.data.get('category'))
        live = m.Live.objects.create(
            name=name,
            password=password,
            paid=paid,
            quota=quota,
            category=category,
            author=request.user,
        )
        return Response(data=s.LiveSerializer(live).data)

    @detail_route(methods=['POST'])
    def live_end(self, request, pk):
        assert not request.user.is_anonymous, '请先登录'
        live = m.Live.objects.get(pk=pk)
        live.date_end = datetime.now()
        live.save()
        return Response(data=True)

    @detail_route(methods=['POST'])
    def make_comment(self, request, pk):
        assert not request.user.is_anonymous, '请先登录'
        live = m.Live.objects.get(pk=pk)
        watch_log = live.watch_logs.filter(author=request.user).first()
        assert watch_log, '观看记录尚未生成'
        comment = watch_log.comments.create(
            author=request.user,
            content=request.data.get('content'),
        )
        return Response(data=s.CommentSerializer(comment).data)

    @detail_route(methods=['POST'])
    def make_barrage(self, request, pk):
        assert not request.user.is_anonymous, '请先登录'
        # TODO: 在这里需要扣除金币
        live = m.Live.objects.get(pk=pk)
        barrage = live.barrages.create(
            author=request.user,
            content=request.data.get('content'),
        )
        return Response(data=s.LiveBarrageSerializer(barrage).data)

    @detail_route(methods=['POST'])
    def buy_prize(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        prize = m.Prize.objects.get(pk=request.data.get('prize'))
        count = int(request.data.get('count'))
        prize_order = m.PrizeOrder.buy_prize(live, prize, count, request.user)
        return Response(data=s.PrizeOrderSerializer(prize_order).data)

    @detail_route(methods=['POST'])
    def send_active_prize(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        prize = m.Prize.objects.get(pk=request.data.get('prize'))
        count = int(request.data.get('count'))
        source_tag = request.data.get('source_tag')
        prize_order = m.PrizeOrder.send_active_prize(live, prize, count, request.user, source_tag)
        return Response(data=s.PrizeOrderSerializer(prize_order).data)

    @detail_route(methods=['GET'])
    def get_live_diamond_rank(self, request, pk):
        live = m.Live.objects.get(pk=pk)

        members = m.Member.objects.filter(
            user__prizeorders_owned__live_watch_log__live=live,
            user__prizeorders_owned__diamond_transaction__user_debit=live.author,
        ).distinct().all()
        rank = []
        for member in members:
            rank_item = dict()
            amount = m.PrizeOrder.objects.filter(
                author=member.user,
                live_watch_log__live=live,
                diamond_transaction__id__gt=0,
            ).aggregate(amount=models.Sum('diamond_transaction__amount')).get('amount') or 6
            rank_item['amount'] = amount
            rank_item['member'] = s.MemberSerializer(member).data
            rank.append(rank_item)
        return Response(data=sorted(rank, key=lambda item: item['amount'], reverse=True))

    @list_route(methods=['GET'])
    def get_today_mission(self, request):
        data = dict()
        # 当前用户完成完成资料任务
        information_mission_count = m.StarMissionAchievement.objects.filter(
            author=self.request.user,
            type=m.StarMissionAchievement.TYPE_INFORMATION,
        ).count()

        # 当前用户当日完成观看任务次数
        today_watch_mission = m.StarMissionAchievement.objects.filter(
            author=self.request.user,
            type=m.StarMissionAchievement.TYPE_WATCH,
            date_created__date=datetime.now().date(),
        )

        # 當前用戶邀請好友當日的完成次數
        today_invite_mission = m.StarMissionAchievement.objects.filter(
            author=self.request.user,
            type=m.StarMissionAchievement.TYPE_INVITE,
            date_created__date=datetime.now().date(),
        )

        # 当前用户分享任务次数
        today_share_mission = m.StarMissionAchievement.objects.filter(
            author=self.request.user,
            type=m.StarMissionAchievement.TYPE_SHARE,
            date_created__date=datetime.now().date(),
        )

        # 观看任务下次领取倒计时
        watch_mission_time = 0
        # todo 每天要清0
        if m.UserPreference.objects.filter(user=self.request.user, key='watch_mission_time').exists():
            mission_time = m.UserPreference.objects.filter(user=self.request.user,
                                                           key='watch_mission_time').first().value
            if int(mission_time) > 30 * 60:
                watch_mission_time = 30 * 60
            else:
                watch_mission_time = mission_time
        else:
            m.UserPreference.set(self.request.user, 'watch_mission_time', 0)

        data['today_watch_mission_count'] = today_watch_mission.count()
        data['today_share_mission_count'] = today_share_mission.count()
        data['today_invite_mission_count'] = today_invite_mission.count()
        data['information_mission_count'] = information_mission_count
        data['watch_mission_time'] = watch_mission_time
        return Response(data=data)

    @detail_route(methods=['POST'])
    def live_report(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        live.informs.create(
            author=self.request.user,
            inform_type=request.data.get('content'),
            reason=request.data.get('content'),
        )
        return Response(True)

    @detail_route(methods=['GET'])
    def get_watch_logs(self, request, pk):
        live = m.Live.objects.get(id=pk)
        watch_logs = live.watch_logs.exclude(author=live.author)
        return Response(data=s.LiveWatchLogSerializer(watch_logs, many=True).data)


class LiveBarrageViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveBarrage.objects.all()
    serializer_class = s.LiveBarrageSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class LiveWatchLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LiveWatchLog.objects.all()
    serializer_class = s.LiveWatchLogSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        live_id = self.request.query_params.get('live')
        if live_id:
            qs = qs.filter(live=live_id)
        return qs

    @list_route(methods=['POST'])
    def start_watch_log(self, request):
        live_id = request.data.get('live')
        live = m.Live.objects.get(pk=live_id)
        m.LiveWatchLog.enter_live(request.user, live)
        return Response(data=True)

    @list_route(methods=['POST'])
    def leave_live(self, request):
        live_id = request.data.get('live')
        live = m.Live.objects.get(pk=live_id)
        log = live.watch_logs.filter(author=request.user).first()
        log.leave_live()
        return Response(data=True)


class ActiveEventViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActiveEvent.objects.all()
    serializer_class = s.ActiveEventSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        member_id = self.request.query_params.get('member')
        followed_by = self.request.query_params.get('followed_by')
        if member_id:
            member = m.Member.objects.filter(
                user_id=member_id
            ).first()
            if member:
                qs = qs.filter(author=member.user)
        if followed_by:
            user = m.User.objects.filter(id=followed_by).first()
            users_following = user.member.get_follow()
            users_friend = m.Member.objects.filter(user__contacts_related__author=user)
            qs = qs.filter(
                m.models.Q(author__member__in=users_following) |
                m.models.Q(author__member__in=users_friend)
            )
        return qs

    @detail_route(methods=['POST'])
    def like(self, request, pk):
        active_event = m.ActiveEvent.objects.get(pk=pk)
        # 指定目标状态或者反转当前的状态
        is_like = request.data.get('is_like') == '1' if 'is_like' in request.data \
            else not active_event.is_liked_by_current_user()
        active_event.set_like_by(request.user, is_like)
        return Response(data=dict(
            is_like=active_event.is_liked_by_current_user(),
            count_like=active_event.get_like_count(),
        ))


class PrizeCategoryViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeCategory.objects.all()
    serializer_class = s.PrizeCategorySerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)

        normal = self.request.query_params.get('normal')
        special_category = ('活动礼物', '宝盒礼物', 'VIP回馈礼物')
        if normal:
            qs = qs.filter(
                is_active=True,
            ).exclude(
                name__in=special_category
            )
        return qs


class PrizeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Prize.objects.all()
    serializer_class = s.PrizeSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        prize_category_id = self.request.query_params.get('prize_category')
        prize_type = self.request.query_params.get('prize_type')
        if prize_category_id:
            qs = qs.filter(category__id=prize_category_id)
        if prize_type and prize_type == 'NORMAL':
            qs = qs.filter(type=m.Prize.TYPE_NORMAL)
        elif prize_type and prize_type == 'SPECIAL':
            qs = qs.filter(type=m.Prize.TYPE_SPECIAL)
        return qs

    @list_route(methods=['GET'])
    def get_user_active_prize(self, request):
        # 获得当前用户的活动礼物
        me = m.User.objects.get(pk=request.user.id)

        active_category = ('活动礼物', '宝盒礼物', 'VIP回馈礼物')

        prizes = m.Prize.objects.filter(
            category__name__in=active_category,
            transactions__user_debit=me,
            transactions__user_credit=None,
        ).distinct()

        data = dict(
            vip_prize=[],
            box_prize=[],
            active_prize=[],
        )
        for prize in prizes:
            accept = me.prizetransactions_debit.filter(
                prize=prize,
                user_credit=None,
            ).all().aggregate(amount=m.models.Sum('amount')).get('amount') or 0
            send = me.prizetransactions_credit.filter(
                prize=prize,
            ).exclude(
                user_debit__id__gt=0,
            ).all().aggregate(amount=m.models.Sum('amount')).get('amount') or 0
            count = int(accept - send)
            if count > 0 and prize.category.name == '活动礼物':
                data['active_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))
            elif count > 0 and prize.category.name == '宝盒礼物':
                data['box_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))
            elif count > 0 and prize.category.name == 'VIP回馈礼物':
                data['vip_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))
        return Response(data=data)

    @list_route(methods=['GET'])
    def get_user_prize_emoji(self, request):
        # todo 获得当前用户送过的礼物没过期的表情包
        prize = m.Prize.objects.filter(
            date_sticker_begin__lt=datetime.now(),
            date_sticker_end__gt=datetime.now(),
            orders__author=request.user,
        ).exclude(stickers=None)

        return Response(data=True)


class PrizeTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeTransaction.objects.all()
    serializer_class = s.PrizeTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def open_star_box(self, request):
        # 观众开星光宝盒
        m.PrizeTransaction.viewer_open_starbox(request.user.id)
        return Response(True)


class PrizeOrderViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeOrder.objects.all()
    serializer_class = s.PrizeOrderSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        member_id = self.request.query_params.get('member')
        live_id = self.request.query_params.get('live')
        if member_id:
            member = m.Member.objects.filter(user=member_id).first()
            if member:
                qs = qs.filter(author=member.user)
        if live_id:
            live = m.Live.objects.filter(id=live_id).first()
            if live:
                qs = qs.filter(live_watch_log__live=live)
        return qs


class ExtraPrizeViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ExtraPrize.objects.all()
    serializer_class = s.ExtraPrizeSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class StatisticRuleViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StatisticRule.objects.all()
    serializer_class = s.StatisticRuleSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class ActivityViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Activity.objects.all()
    serializer_class = s.ActivitySerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        activity_type = self.request.query_params.get('activity_type')
        if activity_type:
            qs = qs.filter(type=activity_type)
        return qs


class ActivityParticipationViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActivityParticipation.objects.all()
    serializer_class = s.ActivityParticipationSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class NotificationsViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Notifications.objects.all()
    serializer_class = s.NotificationsSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class VisitLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.VisitLog.objects.all()
    serializer_class = s.VisitLogSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class MovieViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Movie.objects.all()
    serializer_class = s.MovieSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class StarBoxViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarBox.objects.all()
    serializer_class = s.StarBoxSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class StarBoxRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarBoxRecord.objects.all()
    serializer_class = s.StarBoxRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def open_star_box(self, request):
        user = self.request.user
        live = m.Live.objects.get(pk=request.data.get('live'))
        identity = request.data.get('identity')
        record = m.StarBoxRecord.open_star_box(user, live, identity)
        if record.coin_transaction:
            return response_success('獲得金幣{}'.format(record.coin_transaction.amount))
        elif record.diamond_transaction:
            return response_success('獲得鑽石{}'.format(record.diamond_transaction.amount))
        elif record.prize_transaction:
            return response_success(
                '獲得禮物{}{}個'.format(record.prize_transaction.prize.name, record.prize_transaction.amount))
        return Response(True)


class RedBagRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.RedBagRecord.objects.all()
    serializer_class = s.RedBagRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class StarMissionAchievementViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.StarMissionAchievement.objects.all()
    serializer_class = s.StarMissionAchievementSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def achievement_watch_mission(self, request):
        # 领取观看直播任务奖励
        assert self.request.user.member.get_today_watch_mission_count() < 8, '直播間觀看任務只能做8次'
        # 领取记录
        m.StarMissionAchievement.objects.create(
            author=self.request.user,
            points=5,
            type=m.StarMissionAchievement.TYPE_WATCH,
        )
        # 元气流水
        m.CreditStarTransaction.objects.create(
            user_debit=self.request.user,
            amount=5,
            remark='完成直播間觀看任務',
            type='EARNING',
        )
        # 重置观看任务时间
        preference = m.UserPreference.objects.filter(
            user=self.request.user,
            key='watch_mission_time',
        ).first()
        preference.value = 0
        preference.save()

        return Response(True)


class LevelOptionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LevelOption.objects.all()
    serializer_class = s.LevelOptionSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class InformViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Inform.objects.all()
    serializer_class = s.InformSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class FeedbackViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Feedback.objects.all()
    serializer_class = s.FeedbackSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class BannerViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Banner.objects.all()
    serializer_class = s.BannerSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class SensitiveWordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.SensitiveWord.objects.all()
    serializer_class = s.SensitiveWordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class DiamondExchangeRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.DiamondExchangeRecord.objects.all()
    serializer_class = s.DiamondExchangeRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def diamond_exchange_coin(self, request):
        # 钻石兑换金币
        coin_count = request.data.get('coin_count')
        m.DiamondExchangeRecord.diamond_exchange_coin(request.user, coin_count)
        return Response(True)


class CommentViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Comment.objects.all()
    serializer_class = s.CommentSerializer
    ordering = ['-pk']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        activeevent_id = self.request.query_params.get('activeevent')
        live_id = self.request.query_params.get('live')
        if activeevent_id:
            qs = qs.filter(activeevents__id=activeevent_id,
                           is_active=True, ).order_by('-date_created')
        if live_id:
            qs = qs.filter(livewatchlogs__live__id=live_id,
                           is_active=True, ).order_by('-date_created')
        return qs

    @list_route(methods=['POST'])
    def add_comment(self, request):
        activeevent_id = request.data.get('activeevent')
        content = request.data.get('content')

        if activeevent_id:
            activeevent = m.ActiveEvent.objects.get(pk=activeevent_id)
            activeevent.comments.create(author=self.request.user, content=content)

        return Response(data=True)

    @list_route(methods=['POST'])
    def change_watch_status(self, request):
        comment_id = request.data.get('id')
        watch_status = request.data.get('watch_status')

        if comment_id and watch_status:
            comment = m.Comment.objects.get(pk=comment_id)
            livewatchlog = comment.livewatchlogs.first()
            livewatchlog.status = watch_status
            livewatchlog.save()

        return Response(data=True)


class UserMarkViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.UserMark.objects.all()
    serializer_class = s.UserMarkSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        activeevent_id = self.request.query_params.get('activeevent')
        if activeevent_id:
            qs = qs.filter(
                object_id=activeevent_id,
                subject='like',
                content_type=m.ContentType.objects.get(model='activeevent'),
            ).order_by('-date_created')
        return qs


class ContactViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Contact.objects.all()
    serializer_class = s.ContactSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class AccountTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.AccountTransaction.objects.all()
    serializer_class = s.AccountTransactionSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        nickname = self.request.query_params.get('nickname')
        mobile = self.request.query_params.get('mobile')
        if nickname:
            qs = qs.filter(
                m.models.Q(user_debit__member__nickname__contains=nickname) |
                m.models.Q(user_credit__member__nickname__contains=nickname)
            )
        if mobile:
            qs = qs.filter(
                m.models.Q(user_debit__member__mobile__contains=mobile) |
                m.models.Q(user_credit__member__mobile__contains=mobile)
            )
        return qs

    @list_route(methods=['GET'])
    def get_total_recharge(self, request):
        data = m.AccountTransaction.objects.filter(type=m.AccountTransaction.TYPE_RECHARGE).aggregate(
            amount=models.Sum('amount')).get('amount') or 0
        return Response(data=data)

    @list_route(methods=['GET'])
    def get_total_withdraw(self, request):
        # todo 未进行对美元折算
        data = m.AccountTransaction.objects.filter(
            type=m.AccountTransaction.TYPE_WITHDRAW,
            withdraw_record__status=m.WithdrawRecord.STATUS_PENDING
        ).aggregate(amount=models.Sum('amount')).get('amount') or 0
        return Response(data=data)


class WithdrawRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.WithdrawRecord.objects.all()
    serializer_class = s.WithdrawRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['POST'])
    def withdraw_approve(self, request):
        withdraw_record_id = request.data.get('withdraw_record')
        status = request.data.get('status')
        if withdraw_record_id:
            withdraw_record = m.WithdrawRecord.objects.get(id=withdraw_record_id)
            if status and status == 'APPROVED':
                withdraw_record.approve(self.request.user)
            elif status and status == 'REJECTED':
                withdraw_record.reject(self.request.user)

        return Response(data=True)

    @list_route(methods=['POST'])
    def add_withdraw_blacklisted(self, request):
        author_id = request.data.get('author')
        if author_id:
            member = m.Member.objects.get(user_id=author_id)
            member.add_withdraw_blacklisted()

        return Response(data=True)


class RankRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.RankRecord.objects.all()
    serializer_class = s.RankRecordSerializer
    permission_classes = [p.IsAdminOrReadOnly]

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        rank_type = self.request.query_params.get('rank_type')
        duration = self.request.query_params.get('duration')
        if rank_type and duration:
            qs = qs.filter(duration=duration).order_by('-{}'.format(rank_type))
        return qs


class AdminLogViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.AdminLog.objects.all()
    serializer_class = s.AdminLogSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


class OptionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Option.objects.all()
    serializer_class = s.OptionSerializer
    ordering = ['-pk']

    @list_route(methods=['GET'])
    def get_guide_image(self, request):
        option=[]
        if m.Option.get('guide_page'):
            option = json.loads(m.Option.get('guide_page'))
        images = m.ImageModel.objects.filter(
            id__in=option,
        ).all()
        data = []
        for image in images:
            data.append(image.url())

        return Response(data=data)
