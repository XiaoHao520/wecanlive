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

    @list_route(methods=['POST'])
    def get_guide_page(self, request):
        guide_page_arr = request.data.get('guide_page_arr')
        data = []
        if guide_page_arr:
            for guide_page_id in guide_page_arr:
                data.append(s.ImageSerializer(m.ImageModel.objects.get(pk=guide_page_id)).data)
        return Response(data=data)


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
            name='sender',
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
        chat = self.request.query_params.get('chat')
        target = self.request.query_params.get('target')

        if family:
            qs = qs.filter(families__id=family).order_by('date_created')
        if chat:
            qs = qs.filter(
                m.models.Q(sender__id=chat, receiver=self.request.user) |
                m.models.Q(sender=self.request.user, receiver__id=chat)
            ).order_by('date_created')
        if target and target == 'activity':
            qs = qs.filter(
                broadcast__target=m.Broadcast.TARGET_ACTIVITY,
            ).order_by('date_created')
        if target and target == 'system':
            qs = qs.filter(
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM) |
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_FAMILYS) |
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_NOT_FAMILYS)
            ).order_by('date_created')
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

    @list_route(methods=['POST'])
    def read_message(self, request):
        last_id = request.data.get('last_id')
        sender = m.User.objects.get(id=request.data.get('sender'))
        messages = m.Message.objects.filter(
            sender=sender,
            receiver=self.request.user,
            id__gt=last_id,
            is_read=False,
        ).all()
        for message in messages:
            message.is_read = True
            message.save()
        return Response(data=True)

    @list_route(methods=['POST'])
    def read_system_message(self, request):
        last_id = request.data.get('last_id')
        target = request.data.get('target')
        messages = []
        if target == 'system':
            messages = m.Message.objects.filter(
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM,
                           sender=None,
                           receiver=self.request.user,
                           is_read=False, ) |
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_NOT_FAMILYS,
                           sender=None,
                           receiver=self.request.user,
                           is_read=False, ) |
                m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_FAMILYS,
                           sender=None,
                           receiver=self.request.user,
                           is_read=False, )
            )
        elif target == 'activity':
            messages = m.Message.objects.filter(
                sender=None,
                receiver=self.request.user,
                is_read=False,
                broadcast__target=m.Broadcast.TARGET_ACTIVITY,
            )

        for message in messages:
            message.is_read = True
            message.save()

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

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        target = self.request.query_params.get('target_type')
        if target == 'TARGET_LIVE':
            qs = qs.filter(target=target)
        elif target == 'TARGET_SYSTEM':
            qs = qs.filter(
                m.models.Q(target='TARGET_SYSTEM') |
                m.models.Q(target='TARGET_SYSTEM_FAMILYS') |
                m.models.Q(target='TARGET_SYSTEM_NOT_FAMILYS')
            )
        return qs

    def perform_create(self, serializer):
        # 保存的时候自动发送
        broadcast = serializer.save()
        broadcast.send()

    @list_route(methods=['POST'])
    def create_live_broadcast(self, request):
        content = request.data.get('content')
        print(content)
        users = m.User.objects.filter(
            m.models.Q(livewatchlogs_owned__date_leave=None) |
            m.models.Q(
                livewatchlogs_owned__date_leave__lt=m.models.F('livewatchlogs_owned__date_enter')),
            livewatchlogs_owned__id__gt=0,
        ).distinct().all()
        broadcast = m.Broadcast.objects.create(
            target=m.Broadcast.TARGET_LIVE,
            content=content,
        )
        for user in users:
            broadcast.users.add(user)
        broadcast.send()
        return Response(True)

    @list_route(methods=['POST'])
    def create_system_broadcast(self, request):
        content = request.data.get('content')
        target = request.data.get('target')
        if target == m.Broadcast.TARGET_SYSTEM or target == m.Broadcast.TARGET_ACTIVITY:
            users = m.User.objects.all()
        elif target == m.Broadcast.TARGET_SYSTEM_FAMILYS:
            users = m.User.objects.filter(
                familymembers_owned__gt=0,
            ).distinct().all()
        elif target == m.Broadcast.TARGET_SYSTEM_NOT_FAMILYS:
            users = m.User.objects.exclude(
                familymembers_owned__gt=0,
            ).distinct().all()
        elif target == m.Broadcast.TARGET_LIVE:
            users = m.User.objects.filter(
                m.models.Q(livewatchlogs_owned__date_leave=None) |
                m.models.Q(
                    livewatchlogs_owned__date_leave__lt=m.models.F('livewatchlogs_owned__date_enter')),
                livewatchlogs_owned__id__gt=0,
            ).distinct().all()
        broadcast = m.Broadcast.objects.create(
            target=target,
            content=content,
        )
        for user in users:
            broadcast.users.add(user)
        broadcast.send()
        return Response(True)


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

        # 单点登录处理
        if hasattr(user, 'member'):
            member = user.member
            session_key = request.session.session_key
            # 这说明这个用户已经在其他地方登录过
            if member.session_key and session_key != member.session_key:
                from django.contrib.sessions.models import Session
                # 删除 Session 使原来的登录失效
                Session.objects.filter(session_key=member.session_key).delete()
            member.session_key = session_key
            member.save()

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

        # 单点登录处理
        if hasattr(user, 'member'):
            member = user.member
            session_key = request.session.session_key
            # 这说明这个用户已经在其他地方登录过
            if member.session_key and session_key != member.session_key:
                from django.contrib.sessions.models import Session
                # 删除 Session 使原来的登录失效
                Session.objects.filter(session_key=member.session_key).delete()
            member.session_key = session_key
            member.save()

        m.LoginRecord.make(user)

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
            return response_fail('需要登录', silent=True)
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

        # 单点登录处理
        if hasattr(user, 'member'):
            member = user.member
            session_key = request.session.session_key
            # 这说明这个用户已经在其他地方登录过
            if member.session_key and session_key != member.session_key:
                from django.contrib.sessions.models import Session
                # 删除 Session 使原来的登录失效
                Session.objects.filter(session_key=member.session_key).delete()
            member.session_key = session_key
            member.save()

        m.LoginRecord.make(user)

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

    # @list_route(methods=['get'])
    # def get_chat_list(self, request):
    #     """ 获取聊天列表
    #     所有和自己发过消息的人的列表
    #     附加最近发布过的消息，按照从新到旧的顺序排列
    #     :return:
    #     """
    #
    #     me = request.user
    #     sql = '''
    #     select u.*, max(m.date_created) last_date
    #     from auth_user u, core_base_message m
    #     where u.id = m.author_id and m.receiver_id = %s
    #       or u.id = m.receiver_id and m.author_id = %s
    #     group by u.id
    #     order by max(m.date_created) desc
    #     '''
    #
    #     users = m.user.objects.raw(sql, [me.id, me.id])
    #
    #     data = []
    #     for user in users:
    #         message = m.message.objects.filter(
    #             m.models.q(author=user, receiver=me) |
    #             m.models.q(author=me, receiver=user)
    #         ).order_by('-date_created').first()
    #         avatar = user.member.avatar
    #         unread_count = m.message.objects.filter(
    #             author=user,
    #             receiver=me,
    #             is_read=false,
    #         ).count()
    #         data.append(dict(
    #             id=user.id,
    #             first_name=user.first_name,
    #             last_name=user.last_name,
    #             message_date=message.date_created.strftime('%y-%m-%d %h:%m:%s'),
    #             message_content='[图片]' if message.type == m.message.type_image else
    #             '[商品]' if message.type == m.message.type_object else message.content,
    #             avatar=avatar and avatar.image.url,
    #             nickname=user.member.nickname,
    #             unread_count=unread_count,
    #         ))
    #     return response(data=data)

        # users = m.user.filter(
        #     m.models.q(messages_owned__receiver=me) |
        #     m.models.q(messages_received__author=me)
        # ).annotate(
        #     last_time_sent=max(
        #         m.models.max('messages_owned__date_created'),
        #     ),
        #     last_time_received=max(
        #         m.models.max('messages_received__date_created'),
        #     ),
        #
        #     )
        # )
        #     .order_by('-last_time')

        # users = m.user.objects.all().extra(select={
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
        #         m.models.q(messages_owned__receiver=me) |
        #         m.models.q(messages_received__author=me)) \
        #     .order_by('-last_date')
        #
        # serializer = s.userserializer(data=users, many=true)
        # serializer.is_valid()
        # data = serializer.data
        # for row, user in zip(data, users):
        #     message = m.message.objects.filter(
        #         m.models.q(author=user, receiver=me) |
        #         m.models.q(author=me, receiver=user)
        #     ).order_by('-date_created').first()
        #     row['message_date'] = message.date_created
        #     row['message_text'] = message.content
        # return response(data=data)

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

            # 单点登录处理
            if hasattr(user, 'member'):
                member = user.member
                session_key = request.session.session_key
                # 这说明这个用户已经在其他地方登录过
                if member.session_key and session_key != member.session_key:
                    from django.contrib.sessions.models import Session
                    # 删除 Session 使原来的登录失效
                    Session.objects.filter(session_key=member.session_key).delete()
                member.session_key = session_key
                member.save()

            m.LoginRecord.make(user)

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

    @list_route(methods=['POST'])
    def query_user(self, request):
        account = self.request.data.get('account')
        serverid = self.request.data.get('serverid')
        time = self.request.data.get('time')
        verify = self.request.data.get('verify')
        from hashlib import md5
        str_to_hash = account + serverid + str(time) + settings.WECAN_PAYMENT_VERIFY_KEY
        my_hash = md5(str_to_hash.encode()).hexdigest()
        if my_hash.upper() != verify.upper():
            return Response(data=dict(code='1', msg='verify incorrect'))
        user = m.User.objects.filter(username=account).first()
        if not user:
            return Response(data=dict(code='1', msg='Account not exist'))
        return Response(data=dict(
            code='0',
            account=user.username,
            charname=user.member.nickname,
            level=user.member.get_level() or 0,
            gmoney=user.member.get_coin_balance() or 0,
        ))


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
        is_blacklist = self.request.query_params.get('is_blacklist')
        new_member = self.request.query_params.get('new_member')
        follow_recommended = self.request.query_params.get('follow_recommended')

        if member_id:
            member = m.Member.objects.filter(user_id=member_id).first()
            if member and is_follow:
                qs = member.get_follow()
            elif member and is_followed:
                qs = member.get_followed()

        if is_blacklist:
            qs = self.request.user.member.get_blacklist()

        invite = self.request.query_params.get('invite')
        if invite:
            qs = qs.filter(user__contacts_owned__user=self.request.user
                           ).exclude(user__contacts_related__author=self.request.user)

        rank_type = self.request.query_params.get('rank_type')

        if rank_type and rank_type == 'rank_diamond':
            # 收到礼物钻石数量
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

        if new_member:
            from django.db.models import Count
            qs = qs.annotate(
                live_count=Count('user__lives_owned')
            ).filter(
                live_count__lte=3,
                live_count__gt=0,
            ).order_by('live_count', '-date_created')

        if follow_recommended:
            me = self.request.user.member
            follow = me.get_follow().all()
            qs = qs.filter(
                is_follow_recommended=True
            ).exclude(
                user=self.request.user
            ).exclude(
                user__in=[member.user for member in follow],
            )

        # 使用鑽石消費排行
        diamond_rank = self.request.query_params.get('diamond_rank')
        if diamond_rank and diamond_rank == 'credit':
            qs = m.Member.objects.annotate(
                credit_diamond_amount=m.models.Sum('user__prizeorders_owned__diamond_transaction__amount')
            ).filter(credit_diamond_amount__gt=0)

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

    @detail_route(methods=['POST'])
    def cancel_follow(self, request, pk):
        me = m.Member.objects.get(pk=pk)
        member = request.data.get('member')
        follow_mark = m.UserMark.objects.filter(author=me.user, subject='follow', object_id=member)
        if follow_mark.exists():
            follow_mark.first().delete()

        return Response(data=True)

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
        return Response(data=sorted(rank, key=lambda item: item['amount'], reverse=True)[:3])

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
                prize_orders_as_receiver__id__gt=0,
            )
            if prize_transaction.exists():
                amount = prize_transaction.all().aggregate(amount=m.models.Sum('amount')).get('amount') or 0

                first_pk = prize_transaction.order_by('pk').first().pk

                author = m.PrizeOrder.objects.filter(
                    receiver_prize_transaction__prize=prize,
                    receiver_prize_transaction__user_debit=user,
                    receiver_prize_transaction__user_credit=user,
                    sender_prize_transaction__id__gt=0,
                ).order_by('pk').first().author

                item = dict(
                    prize=s.PrizeSerializer(prize).data,
                    amount=amount,
                    first_pk=first_pk,
                    author_avatar=author.member.avatar.image.url if author.member.avatar else None,
                )
                data.append(item)
        return Response(data=sorted(data, key=lambda item: item['first_pk'], reverse=True))

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
        from auth_user u, base_message m
        where u.id = m.sender_id and m.receiver_id = %s
          or u.id = m.receiver_id and m.sender_id = %s
        group by u.id
        order by max(m.date_created) desc
        '''

        users = m.User.objects.raw(sql, [me.id, me.id])
        data = []

        for user in users:
            message = m.Message.objects.filter(
                m.models.Q(sender=user, receiver=me) |
                m.models.Q(sender=me, receiver=user)
            ).order_by('-date_created').first()
            unread_count = m.Message.objects.filter(
                sender=user,
                receiver=me,
                is_read=False,
            ).count()
            data.append(dict(
                id=user.id,
                nickname=user.member.nickname,
                date_created=message.date_created,
                message_countent=message.content,
                avatar=s.ImageSerializer(user.member.avatar).data['image'],
                type='chat'
            ))

        # 最新跟蹤信息
        follow_user_mark = m.UserMark.objects.filter(
            object_id=self.request.user.id,
            subject='follow',
            content_type=m.ContentType.objects.get(model='member'),
        ).order_by('-date_created')
        if follow_user_mark.exists():
            data.append(dict(
                type='follow',
                message_content='{} 追蹤了你'.format(follow_user_mark.first().author.member.nickname),
                is_read=True,
                date_created=follow_user_mark.first().date_created,
            ))
        # 最新動態消息
        activeevents = self.request.user.activeevents_owned.all()
        like_activeevent_mark = m.UserMark.objects.filter(
            object_id__in=[activeevent.id for activeevent in activeevents],
            subject='like',
            content_type=m.ContentType.objects.get(model='activeevent'),
        ).order_by('-date_created').first()
        activeevent_comment = m.Comment.objects.filter(
            activeevents__id__in=[activeevent.id for activeevent in activeevents],
        ).order_by('-date_created').first()
        last_activeevent_message = None
        if like_activeevent_mark and activeevent_comment:
            if like_activeevent_mark.date_created > activeevent_comment.date_created:
                last_activeevent_message = 'mark'
            else:
                last_activeevent_message = 'comment'
        else:
            last_activeevent_message = 'mark' if like_activeevent_mark else 'comment' if activeevent_comment else None
        if last_activeevent_message and last_activeevent_message == 'mark':
            data.append(dict(
                date_created=like_activeevent_mark.date_created,
                message_content='{} 給你點了一個讃'.format(like_activeevent_mark.author.member.nickname),
                type='activeevent',
                is_read=True,
            ))

        if last_activeevent_message and last_activeevent_message == 'comment':
            data.append(dict(
                date_created=activeevent_comment.date_created,
                message_content=activeevent_comment.content,
                type='activeevent',
                is_read=True,
            ))

        # 活動消息
        activity_message = m.Message.objects.filter(
            sender=None,
            receiver=self.request.user,
            broadcast__target=m.Broadcast.TARGET_ACTIVITY,
        ).order_by('-date_created')
        if activity_message.exists():
            data.append(dict(
                date_created=activity_message.first().date_created,
                message_content=activity_message.first().content,
                is_read=activity_message.first().is_read,
                type='activity',
            ))

        # 家族消息


        return Response(data=sorted(data, key=lambda item: item['date_created'], reverse=True))

    @list_route(methods=['POST'])
    def member_inform(self, request):
        # 舉報用戶
        member = m.User.objects.get(id=request.data.get('member')).member
        member.informs.create(
            author=self.request.user,
            reason=request.data.get('content'),
        )
        return Response(data=True)

    @list_route(methods=['POST'])
    def set_member_blacklist(self, request):
        member = m.User.objects.get(id=request.data.get('member')).member
        is_black = False
        if request.data.get('is_black') and request.data.get('is_black') == '1':
            is_black = True
        member.set_blacklist_by(self.request.user, is_black)
        return Response(data=True)

    @list_route(methods=['POST'])
    def update_search_history(self, request):
        keyword = request.data.get('keyword')
        if keyword:
            self.request.user.member.update_search_history(keyword)
        return Response(data=True)

    @list_route(methods=['GET'])
    def get_system_message_list(self, request):
        # 获得系统消息列表
        # 最新系統信息
        system_message = m.Message.objects.filter(
            m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM,
                       sender=None, receiver=self.request.user, ) |
            m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_NOT_FAMILYS,
                       sender=None, receiver=self.request.user, ) |
            m.models.Q(broadcast__target=m.Broadcast.TARGET_SYSTEM_FAMILYS,
                       sender=None, receiver=self.request.user, )
        ).order_by('-date_created')
        last_system_message = None
        if system_message.exists():
            last_system_message = dict(
                date_created=system_message.first().date_created,
                content=system_message.first().content,
                is_read=system_message.first().is_read,
            )
            # 最新活動信息
            # activity_message = m.Message.objects.filter(
            #     sender=None,
            #     receiver=self.request.user,
            #     broadcast__target=m.Broadcast.TARGET_ACTIVITY,
            # ).order_by('-date_created')
            # last_active_message = None
            # if activity_message.exists():
            #     last_active_message = dict(
            #         date_created=activity_message.first().date_created,
            #         content=activity_message.first().content,
            #         is_read=activity_message.first().is_read,

            # )
        # # 最新动态通知
        # last_activeevent_message = None
        # like_usermark_date = None
        # active_comment_date = None
        # activeevents = self.request.user.activeevents_owned.all()
        # like_usermark = m.UserMark.objects.filter(
        #     object_id__in=[activeevent.id for activeevent in activeevents],
        #     subject='like',
        #     content_type=m.ContentType.objects.get(model='activeevent'),
        # ).order_by('-date_created').first()
        # active_comment = m.Comment.objects.filter(
        #     activeevents__id__in=[activeevent.id for activeevent in activeevents],
        # ).order_by('-date_created').first()
        # if like_usermark:
        #     like_usermark_date = like_usermark.date_created
        # if active_comment:
        #     active_comment_date = active_comment.date_created
        #
        # if active_comment_date and active_comment_date > like_usermark_date:
        #     last_activeevent_message = dict(
        #         date_created=active_comment.date_created,
        #         content=active_comment.content,
        #         is_read=True,
        #     )
        # else:
        #     last_activeevent_message = dict(
        #         date_created=like_usermark.date_created,
        #         content='{}給你點了一個贊'.format(like_usermark.author.member.nickname),
        #         is_read=True,
        #     )

        # # 最新跟踪信息
        # follow_user_mark = m.UserMark.objects.filter(
        #     object_id=self.request.user.id,
        #     subject='follow',
        #     content_type=m.ContentType.objects.get(model='member')
        # ).order_by('-date_created')
        # last_follow_message = None
        # if follow_user_mark.exists():
        #     last_follow_message = dict(
        #         date_created=follow_user_mark.first().date_created,
        #         content='{}.追蹤了你'.format(follow_user_mark.first().author.member.nickname),
        #         is_read=True,
        #     )
        return Response(data=last_system_message)

    @list_route(methods=['GET'])
    def get_prize_emoji(self, request):
        return Response(data=True)

    @list_route(methods=['GET'])
    def check_view_member(self, request):
        # 查看谁看过我的列表中的会员卡
        me = self.request.user.member
        member = m.User.objects.get(pk=request.query_params.get('member_id')).member
        results = me.update_check_member_history(member)
        if not results:
            return response_fail('', 50001, silent=True)
        return Response(data=s.MemberSerializer(results).data)

    @list_route(methods=['GET'])
    def get_increased_chart_data(self, request):
        """
        数据分析 - 新增用户
        :param request:
        :return:
        """
        time_begin = self.request.query_params.get('time_begin')
        time_end = self.request.query_params.get('time_end')
        if not time_begin or not time_end:
            return response_fail('請填寫完整的時間區間')
        begin = datetime.strptime(time_begin, '%Y-%m-%d')
        end = datetime.strptime(time_end, '%Y-%m-%d')
        duration = end - begin
        data = None
        labels = []
        amounts = []
        if duration.days < 31:
            for i in range(duration.days + 1):
                label_item = '{}月{}號'.format(
                    (begin + timedelta(days=i)).month, (begin + timedelta(days=i)).day)
                amount_item = m.Member.objects.filter(
                    date_created__gt=begin + timedelta(days=i),
                    date_created__lt=begin + timedelta(days=i + 1)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        elif 31 < duration.days < 62:
            for i in range(int(duration.days / 7)):
                label_item = '{}月{}號 - {}月{}號'.format(
                    (begin + timedelta(days=i * 7)).month,
                    (begin + timedelta(days=i * 7)).day,
                    (begin + timedelta(days=(i + 1) * 7)).month,
                    (begin + timedelta(days=(i + 1) * 7)).day,
                )
                amount_item = m.Member.objects.filter(
                    date_created__gt=begin + timedelta(days=i * 7),
                    date_created__lt=begin + timedelta(days=(i + 1) * 7)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
                if i == int(duration.days / 7) - 1 and duration.days % 7 > 0:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        (begin + timedelta(days=(i + 1) * 7)).month,
                        (begin + timedelta(days=(i + 1) * 7)).day,
                        end.month,
                        end.day,
                    )
                    amount_item = m.Member.objects.filter(
                        date_created__gt=begin + timedelta(days=(i + 1) * 7),
                        date_created__lt=end + timedelta(days=1),
                    ).count()
                    labels.append(label_item)
                    amounts.append(amount_item)
        elif 62 < duration.days <= 366:
            for i in range(int(duration.days / 31) + 2):
                if i == 0 and begin.day != 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        begin.month,
                        begin.day,
                        1 if begin.month == 12 else begin.month + 1,
                        1,
                    )
                    amount_item = m.Member.objects.filter(
                        date_created__gt=begin,
                        date_created__lt=datetime(begin.year + 1, 1, 1) if begin.month == 12 else datetime(
                            begin.year, begin.month + 1, 1),
                    ).count()
                elif i == int(duration.days / 31) + 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        1 if begin.month + i == 12 else (begin.month + i) % 12,
                        1,
                        end.month,
                        end.day,
                    )
                    amount_item = m.Member.objects.filter(
                        date_created__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                  1) if begin.month + i > 12 else datetime(begin.year,
                                                                                           begin.month + i, 1),
                        date_created__lt=end + timedelta(days=1)
                    ).count()
                else:
                    label_item = '{}月1號 - {}月1號'.format(
                        begin.month + i if begin.month + i <= 12 else (begin.month + i) % 12,
                        begin.month + i + 1 if begin.month + i + 1 <= 12 else (begin.month + i + 1) % 12,
                    )
                    amount_item = m.Member.objects.filter(
                        date_created__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                  1) if begin.month + i > 12 else datetime(
                            begin.year, begin.month + i, 1),
                        date_created__lt=datetime(begin.year + 1, (begin.month + i + 1) % 12,
                                                  1) if begin.month + i + 1 > 12 else datetime(
                            begin.year, begin.month + i + 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        else:
            for i in range(int(duration.days / 365) + 1):
                label_item = '{}年'.format(begin.year + i)
                if i == 0:
                    amount_item = m.Member.objects.filter(
                        date_created__gt=begin,
                        date_created__lt=datetime(begin.year + 1, 1, 1)
                    ).count()
                elif i == duration.days / 365:
                    amount_item = m.Member.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=end,
                    ).count()
                else:
                    amount_item = m.Member.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=datetime(begin.year + i + 1, 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        data = dict(
            labels=labels,
            amounts=amounts,
        )
        return Response(data=data)

    @list_route(methods=['GET'])
    def get_gender_chart_data(self, request):
        """
        用戶性別、年齡比
        :param request:
        :return:
        """
        gender = self.request.query_params.get('gender')
        labels = []
        amounts = []
        data = None
        count_member = m.Member.objects.all().count()
        for i in range(20):
            if i < 19:
                label_item = '{}~{}歲'.format(i * 5, (i + 1) * 5 - 1)
            else:
                label_item = '>95歲'
            labels.append(label_item)
            amount_item = m.Member.objects.filter(
                gender=gender,
                age__gte=i * 5,
                age__lte=(i + 1) * 5 - 1,
            ).count()
            amounts.append(amount_item / count_member)
        data = dict(labels=labels, amounts=amounts)
        return Response(data=data)

    @detail_route(methods=['POST'])
    def find_referrer_member(self, request, pk):
        # 尋找邀请自己的会员
        me = m.User.objects.get(pk=pk).member
        assert not me.referrer, '你已經填寫過邀請人，不能再填寫。'
        assert not me.user.id == int(request.data.get('referrer')), '不能設置自己爲邀請人'
        member = m.Member.objects.filter(user__id=request.data.get('referrer'))
        if not member.exists():
            return response_fail('沒有用戶', 50010, silent=True)
        return Response(data=s.MemberSerializer(member.first()).data)

    @detail_route(methods=['POST'])
    def set_referrer_member(self, request, pk):
        # 設置邀请自己的会员
        me = m.User.objects.get(pk=pk).member
        assert not me.referrer, '你已經填寫過邀請人，不能再填寫。'
        assert not me.user.id == int(request.data.get('referrer')), '不能設置自己爲邀請人'
        member = m.Member.objects.filter(user__id=request.data.get('referrer')).first()
        me.referrer = member.user
        me.save()
        # todo
        m.CreditStarTransaction.objects.create(
            user_debit=member.user,
            amount=40,
            type=m.CreditStarTransaction.TYPE_EARNING,
            remark='邀請好友獲得',
        )
        return Response(data=True)

    @list_route(methods=['GET'])
    def get_qrcode(self, request):
        from urllib.request import urlopen
        from django.core.files import File
        from django.core.files.temp import NamedTemporaryFile
        code_type = self.request.query_params.get('type')
        id = self.request.query_params.get('object_id')
        member = None
        family = None
        if not code_type:
            return
        if code_type == 'member':
            member = m.Member.objects.get(user=id)
            if member.qrcode:
                return Response(data=member.qrcode.url())
        if code_type == 'family':
            family = m.Family.objects.get(id=id)
            if family.qrcode:
                return Response(data=family.qrcode.url())
        url = 'http://qr.liantu.com/api.php?text=wecan_membercode-{}-{}-wecan_membercode&fg=0B1171{}'.format(
            code_type,
            id,
            '&logo=' if None else '',
        )
        img_temp = NamedTemporaryFile(delete=True)
        img_temp.write(urlopen(url).read())
        img_temp.flush()
        image = m.ImageModel.objects.create(
            image=File(img_temp, name='qrcode_{}_{}_{}.png'.format(code_type, id, random.randint(1e8, 1e9))),
        )
        if member:
            member.qrcode = image
            member.save()
            return Response(data=image.url())
        if family:
            family.qrcode = image
            family.save()
            return Response(data=image.url())


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
                # user_debit_id=F('user_credit_id'),
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

    @detail_route(methods=['GET'])
    def family_mission_achievement(self, request, pk):
        family_mission = m.FamilyMission.objects.get(pk=pk)
        achievement = m.FamilyMissionAchievement.objects.filter(
            author=self.request.user,
            mission=family_mission,
        )
        if not achievement.exists():
            # 還沒領取任務
            return Response(data='UNRECEIVED')

        if achievement.first().status == m.FamilyMissionAchievement.STATUS_START:
            # 已經領取任務，檢測是否滿足條件
            check_mission_achievement = achievement.first().check_mission_achievement()
            if check_mission_achievement:
                # 已经完成任务，未领取奖励
                return Response(data='ACHIEVE')
            else:
                # 未完成任务
                return Response(data='START')
        if achievement.first().status == m.FamilyMissionAchievement.STATUS_ACHIEVE:
            # 已经完成任务，未领取奖励
            return Response(data='ACHIEVE')
        if achievement.first().status == m.FamilyMissionAchievement.STATUS_FINISH:
            # 已经领取奖励
            return Response(data='FINISH')
        return Response(data=True)


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
        from django.db.models import Count
        qs = interceptor_get_queryset_kw_field(self)
        order = self.request.query_params.get('order')
        if order and order == 'live_count':
            qs = qs.annotate(live_count=Count('lives')).order_by('live_count')
        return qs


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

        id_not_in = self.request.query_params.get('id_not_in')

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

        if id_not_in:
            id_list = [int(x) for x in id_not_in.split(',') if x]
            qs = qs.exclude(pk__in=id_list)

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

    @list_route(methods=['POST'])
    def replay_live(self, request):
        assert not request.user.is_anonymous, '請先登錄'
        live_id = request.data.get('id')
        live = m.Live.objects.filter(
            author=self.request.user,
            id=live_id,
        ).first()
        if not live:
            return Response(data=False)
        live.date_replay = datetime.now()
        live.save()
        return Response(data=True)

    @detail_route(methods=['POST'])
    def live_end(self, request, pk):
        assert not request.user.is_anonymous, '請先登錄'
        live = m.Live.objects.get(pk=pk)
        live.date_end = datetime.now()
        live.save()
        # 计算经验值
        live.live_experience()
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

    @detail_route(methods=['POST'])
    def live_delete(self, request, pk):
        live = m.Live.objects.get(pk=pk)
        assert self.request.user == live.author, '你不是直播主不能刪除此直播間'
        live.is_del = True
        live.save()
        return Response(data=True)


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

    @list_route(methods=['GET'])
    def get_watch_chart_data(self, request):
        labels = []
        amounts = []
        data = None
        category = self.request.query_params.get('category')
        now = datetime.now()
        yesterday = datetime(now.year, now.month, now.day) - timedelta(days=1)
        for i in range(24):
            print(datetime(yesterday.year, yesterday.month, yesterday.day, i))
            label_item = '{:0>2d}:00 - {:0>2d}:00'.format(i, i + 1)
            amount_item = m.LiveWatchLog.objects.filter(
                live__category=category,
                date_enter__gte=datetime(yesterday.year, yesterday.month, yesterday.day, i),
                date_enter__lte=datetime(yesterday.year, yesterday.month, yesterday.day,
                                         i + 1) if i + 1 < 24 else datetime(now.year, now.month, now.day)
            ).count()
            labels.append(label_item)
            amounts.append(amount_item)
        data = dict(labels=labels, amounts=amounts)
        return Response(data=data)


class ActiveEventViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActiveEvent.objects.all()
    serializer_class = s.ActiveEventSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        member_id = self.request.query_params.get('member')
        followed_by = self.request.query_params.get('followed_by')
        hot = self.request.query_params.get('hot')

        id_not_in = self.request.query_params.get('id_not_in')

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
        if hot:
            # 热门动态
            me = self.request.user.member
            follow = me.get_follow().all()
            friend = m.Member.objects.filter(
                m.models.Q(user__contacts_related__author=me.user),
                m.models.Q(user__contacts_owned__user=me.user),
            ).all()
            qs = qs.exclude(
                author__in=[member.user for member in follow],
            ).exclude(
                author__in=[member.user for member in friend],
            ).exclude(
                author=me.user
            ).order_by('-like_count')

        if id_not_in:
            id_list = [int(x) for x in id_not_in.split(',') if x]
            qs = qs.exclude(pk__in=id_list)

        return qs

    @detail_route(methods=['POST'])
    def like(self, request, pk):
        active_event = m.ActiveEvent.objects.get(pk=pk)
        # 指定目标状态或者反转当前的状态
        is_like = request.data.get('is_like') == '1' if 'is_like' in request.data \
            else not active_event.is_liked_by_current_user()
        active_event.set_like_by(request.user, is_like)
        # 统计动态点赞数
        active_event.update_like_count()
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

        m.PrizeTransaction.objects.filter()
        data = dict(
            vip_prize=[],
            box_prize=[],
            active_prize=[],
        )
        # 活动礼物
        activity_prize = m.Prize.objects.filter(
            transactions__user_debit=me,
            transactions__user_credit=None,
            transactions__source_tag=m.PrizeTransaction.SOURCE_TAG_ACTIVITY,
        ).distinct().all()
        # 宝盒礼物
        box_prize = m.Prize.objects.filter(
            transactions__user_debit=me,
            transactions__user_credit=None,
            transactions__source_tag=m.PrizeTransaction.SOURCE_TAG_STAR_BOX,
        ).distinct().all()
        # vip礼物
        vip_prize = m.Prize.objects.filter(
            transactions__user_debit=me,
            transactions__user_credit=None,
            transactions__type=m.PrizeTransaction.TYPE_VIP_GAIN,
            transactions__source_tag=m.PrizeTransaction.SOURCE_TAG_VIP
        ).distinct().all()

        for prize in activity_prize:
            count = prize.get_activity_prize_balance(me, 'ACTIVITY')
            if count > 0:
                data['active_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))
        for prize in box_prize:
            count = prize.get_activity_prize_balance(me, 'STAR_BOX')
            if count > 0:
                data['box_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))
        for prize in vip_prize:
            count = prize.get_activity_prize_balance(me, 'VIP')
            if count > 0:
                data['vip_prize'].append(dict(
                    id=prize.id,
                    icon=prize.icon.image.url,
                    name=prize.name,
                    count=count,
                    price=prize.price,
                    categor=prize.category.name,
                ))

        return Response(data=data)

        # @list_route(methods=['GET'])
        # def get_user_prize_emoji(self, request):
        #     # todo 获得当前用户送过的礼物没过期的表情包
        #     prize = m.Prize.objects.filter(
        #         date_sticker_begin__lt=datetime.now(),
        #         date_sticker_end__gt=datetime.now(),
        #         orders__author=request.user,
        #     ).exclude(stickers=None)
        #
        #     return Response(data=True)


class PrizeTransactionViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PrizeTransaction.objects.all()
    serializer_class = s.PrizeTransactionSerializer
    permission_classes = [p.IsAdminOrReadOnly]
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

        # @list_route(methods=['POST'])
        # def open_star_box(self, request):
        #     # 观众开星光宝盒
        #     m.PrizeTransaction.viewer_open_starbox(request.user.id)
        #     return Response(True)


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

    @detail_route(methods=['POST'])
    def activity_draw_turntable(self, request, pk):
        """ 抽奖活动转盘点击开始抽奖动作
            完成概率抽奖和对应的流水插入等动作，返回1-8抽奖结果给前端的转盘显示
        """
        activity = m.Activity.objects.get(pk=pk)
        if not activity.join_draw_activity(self.request.user):
            return response_fail('您當前還未滿足參與活動的條件，不能參與活動')
        awards = json.loads(activity.rules)['awards']
        r = random.random()
        weight_local = 0
        number = 0
        result = None
        result_number = None
        for award in awards:
            number += 1
            new_weight_local = weight_local + award['weight']
            if weight_local < r <= new_weight_local:
                result = award
                result_number = number
            weight_local = new_weight_local
        # 獎勵
        self.request.user.member.member_activity_award(activity, result['award'])
        return Response(data=dict(
            result_number=result_number,
            result=result,
        ))

    @detail_route(methods=['GET'])
    def get_activity_vote_list(self, request, pk):
        """
            票選活動票數排序名單
        """
        activity = m.Activity.objects.get(pk=pk)
        rules_prize_id = json.loads(activity.rules)['prize']
        prize_transactions = m.PrizeTransaction.objects.filter(
            prize__id=rules_prize_id,
            user_debit=m.models.F('user_credit'),
            prize_orders_as_receiver__id__gt=0,
            prize_orders_as_receiver__date_created__gt=activity.date_begin,
            prize_orders_as_receiver__date_created__lt=activity.date_end,
        ).all()
        members = m.Member.objects.filter(
            user__in=[prize_transaction.user_debit for prize_transaction in prize_transactions]
        )
        data = []
        for member in members:
            prize_amount = member.user.prizetransactions_debit.filter(
                prize__id=rules_prize_id,
                user_debit=m.models.F('user_credit'),
                prize_orders_as_receiver__id__gt=0,
                prize_orders_as_receiver__date_created__gt=activity.date_begin,
                prize_orders_as_receiver__date_created__lt=activity.date_end,
            ).all().aggregate(amount=m.models.Sum('amount')).get('amount') or 0
            data.append(dict(
                member=s.MemberSerializer(member).data,
                amount=prize_amount,
            ))
        return Response(data=sorted(data, key=lambda item: item['amount'], reverse=True)[:20])

    @detail_route(methods=['GET'])
    def get_activity_watch_list(self, request, pk):
        """观看活动观看时长排序列表
        """
        activity = m.Activity.objects.get(pk=pk)
        rules = json.loads(activity.rules)
        watch_logs = m.LiveWatchLog.objects.filter(
            live__date_created__gt=activity.date_begin,
            live__date_created__lt=activity.date_end,
            duration__gt=rules['min_duration'],
        ).all()
        members = m.Member.objects.filter(
            user__in=[watch_log.author for watch_log in watch_logs],
        ).all()
        data = []
        for member in members:
            watch_logs = member.user.livewatchlogs_owned.filter(
                live__date_created__gt=activity.date_begin,
                live__date_created__lt=activity.date_end,
                duration__gt=rules['min_duration'],
            )
            watch_logs_count = watch_logs.count()
            watch_logs_duration = watch_logs.all().aggregate(duration=m.models.Sum('duration')).get('duration') or 0
            if watch_logs_count >= int(rules['min_watch']):
                data.append(dict(
                    member=s.MemberSerializer(member).data,
                    watch_logs_count=watch_logs_count,
                    watch_logs_duration=watch_logs_duration,
                ))

        return Response(data=sorted(data, key=lambda item: item['watch_logs_duration'], reverse=True)[:20])

    @detail_route(methods=['GET'])
    def get_activity_diamond_list(self, request, pk):
        """
        鑽石活動，獲得鑽石數排序
        获奖名单： 已经领取奖励的用户，钻石余额排行
        助力名单： 用户送的钻石排行
        """
        activity = m.Activity.objects.get(pk=pk)
        # 已经领取奖励的用户
        members = m.Member.objects.filter(
            user__activityparticipations_owned__activity=activity,
        ).all()
        receiver_list = []
        send_list = []
        for member in members:
            amount = member.get_diamond_balance()
            receiver_list.append(dict(
                member=s.MemberSerializer(member).data,
                amount=amount,
            ))
        receiver_list = sorted(receiver_list, key=lambda item: item['amount'], reverse=True)[:20]

        return Response(data=receiver_list)

    # @detail_route(methods=['POST'])
    # def activity_award(self, request, pk):
    #     activity = m.Activity.objects.get(pk=pk)
    #     activity.settle()
    #     return Response(data=True)

    @detail_route(methods=['POST'])
    def diamond_activity_receive_award(self, request, pk):
        # 钻石活动领取阶段奖励，
        # 领取奖励之后不能再领取其他阶段奖励
        activity = m.Activity.objects.get(pk=pk)
        me = self.request.user.member
        assert datetime.now() > activity.date_begin, '活動還沒開始'
        assert datetime.now() < activity.date_end and not activity.is_settle, '活動已經結束'
        assert not m.ActivityParticipation.objects.filter(
            activity=activity,
            author__member=me,
        ).exists(), '你已經領取過階段獎勵了，不能再領取其他獎勵'
        # stage 第几阶段
        stage = request.data.get('stage')
        awards = json.loads(activity.rules)['awards']
        stage_award = awards[stage]
        diamond_balance = me.get_diamond_balance()
        assert diamond_balance >= stage_award['from'], '你的鑽石數量不足領取這個階段的獎勵要求'
        me.member_activity_award(activity, stage_award['award'])
        return Response(data=True)


class ActivityPageViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.ActivityPage.objects.all()
    serializer_class = s.ActivityPageSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)


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

    # ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        latest = self.request.query_params.get('latest')
        if latest:
            latest_time = datetime.now() - timedelta(hours=24)
            # 24小时内
            qs = qs.filter(
                date_last_visit__gt=latest_time,
                user=self.request.user,
            ).order_by('-date_last_visit')
        return qs

    @list_route(methods=['post'])
    def visit(self, request):
        guest = m.User.objects.get(id=request.data.get('guest')).member
        host = m.User.objects.get(id=request.data.get('host')).member
        m.VisitLog.visit(guest, host)
        return Response(data=True)


class MovieViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Movie.objects.all()
    serializer_class = s.MovieSerializer
    ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs


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


class Levelet(viewsets.ModelViewSet):
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
        qs = interceptor_get_queryset_kw_field(self)
        # 后台筛选被举报人 ID、账号时，同时能筛选 直播 和 动态
        for key in self.request.query_params:
            value = self.request.query_params[key]
            if key == 'la_lives__author__id':
                key2 = 'la_activeevents__author__id'
                field = key[3:]
                field2 = key2[3:]
                qs = qs.filter(
                    m.models.Q(**{field + '__contains': value}) |
                    m.models.Q(**{field2 + '__contains': value})
                )
            if key == 'la_lives__author__member__mobile':
                key2 = 'la_activeevents__author__member__mobile'
                field = key[3:]
                field2 = key2[3:]
                qs = qs.filter(
                    m.models.Q(**{field + '__contains': value}) |
                    m.models.Q(**{field2 + '__contains': value})
                )
        return qs


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
        own_activeevent_comment = self.request.query_params.get('own_activeevent_comment')

        me = self.request.user
        if activeevent_id:
            qs = qs.filter(activeevents__id=activeevent_id,
                           is_active=True, ).order_by('-date_created')
        if live_id:
            qs = qs.filter(livewatchlogs__live__id=live_id,
                           is_active=True, ).order_by('-date_created')

        if own_activeevent_comment:
            activeevents = me.activeevents_owned.all()
            qs = qs.filter(
                activeevents__id__in=[activeevent.id for activeevent in activeevents],
            ).order_by('-date_created')

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

        own_like_list = self.request.query_params.get('own_like_list')
        # 个人被点赞的usermark列表
        me = self.request.user
        if own_like_list:
            activeevents = me.activeevents_owned.all()
            qs = qs.filter(
                object_id__in=[activeevent.id for activeevent in activeevents],
                subject='like',
                content_type=m.ContentType.objects.get(model='activeevent'),
            ).order_by('-date_created')

        # 被关注列表
        is_followed = self.request.query_params.get('is_followed')
        if is_followed:
            qs = qs.filter(
                object_id=me.id,
                subject='follow',
                content_type=m.ContentType.objects.get(model='member'),
            ).order_by('-date_created')
            # print(qs)

        return qs


class ContactViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.Contact.objects.all()
    serializer_class = s.ContactSerializer

    # ordering = ['-pk']

    def get_queryset(self):
        qs = interceptor_get_queryset_kw_field(self)

        return qs

    @list_route(methods=['POST'])
    def set_disturb(self, request):
        disturb = request.data.get('disturb')
        contact = m.Contact.objects.filter(author=self.request.user,
                                           user__id=request.data.get('member'))
        if not contact.exists():
            return response_fail('你們還不是好友關係')
        setting = contact.first().settings.filter(key='is_not_disturb')
        if setting.exists():
            setting_is_not_disturb = setting.first()
            setting_is_not_disturb.value = disturb
            setting_is_not_disturb.save()
        else:
            contact.first().settings.create(
                key='is_not_disturb',
                value=disturb,
            )

        return Response(data=True)


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
            if rank_type == 'receive_diamond_amount':
                qs = qs.filter(receive_diamond_amount__gt=0)
            if rank_type == 'send_diamond_amount':
                qs = qs.filter(send_diamond_amount__gt=0)
            if rank_type == 'star_index_amount':
                qs = qs.filter(star_index_amount__gt=0)

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
    permission_classes = [p.IsAdminOrReadOnly]

    @list_route(methods=['GET'])
    def all(self, request):
        data = dict()
        for opt in m.Option.objects.all():
            data[opt.key] = opt.value
        return Response(data=data)

    @list_route(methods=['GET'])
    def get(self, request):
        return Response(data=m.Option.get(request.GET.get('name')))

    @list_route(methods=['POST'], permission_classes=[p.IsAdminUser])
    def set(self, request):
        # print(request.data)
        m.Option.set(
            request.data.get('name'),
            request.data.get('value'),
        )
        return Response(data=m.Option.get(request.data.get('name')))

    @list_route(methods=['GET'])
    def get_guide_image(self, request):
        option = []
        if m.Option.get('guide_page'):
            option = json.loads(m.Option.get('guide_page'))
        images = m.ImageModel.objects.filter(
            id__in=option,
        ).all()
        data = []
        for image in images:
            data.append(s.ImageSerializer(image).data['image'])

        return Response(data=data)


class RechargeRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.RechargeRecord.objects.all()
    serializer_class = s.RechargeRecordSerializer
    ordering = ['-pk']

    @list_route(methods=['POST', 'GET'])
    def notify(self, request):
        """
        参照 wecanLive+API+Requirement_20170605 文档
        wecan SDK下单回调
        :return:
        """
        account = self.request.data.get('account') or self.request.query_params.get('account')
        serverid = self.request.data.get('serverid') or self.request.query_params.get('serverid')
        platform = self.request.data.get('platform') or self.request.query_params.get('platform')
        orderid = self.request.data.get('orderid') or self.request.query_params.get('orderid')
        productid = self.request.data.get('productid') or self.request.query_params.get('productid')
        imoney = self.request.data.get('imoney') or self.request.query_params.get('imoney')
        to_account = self.request.data.get('to_account') or self.request.query_params.get('to_account')
        extra = self.request.data.get('extra') or self.request.query_params.get('extra')
        time = self.request.data.get('time') or self.request.query_params.get('time')
        verify = self.request.data.get('verify') or self.request.query_params.get('verify')
        # 验签
        from hashlib import md5
        str_to_hash = account + platform + orderid + str(imoney) + str(time) + settings.WECAN_PAYMENT_VERIFY_KEY
        my_hash = md5(str_to_hash.encode()).hexdigest()
        if my_hash.upper() != verify.upper():
            return Response(data=dict(code='1', msg='verify incorrect'))
        author = m.User.objects.filter(username=account).first()
        if not author:
            return Response(data=dict(code='1', msg='user does not exist'))
        # 入单
        payment_record, is_created = m.PaymentRecord.objects.get_or_create(
            out_trade_no=orderid,
            defaults=dict(
                subject='wecan充值{}'.format(productid),
                amount=imoney,
                author=author,
                platform=m.PaymentRecord.PLATFORM_OTHER,
                product_id=productid or '',
                notify_data='',  # request.body,
            )
        )
        # 订单重复
        if not is_created:
            return Response(data=dict(code='1', msg='record exist'))
        # 记录充值订单
        recharge_record = m.RechargeRecord.objects.create(
            author=author,
            payment_record=payment_record,
            amount=payment_record.amount,
        )
        # 计算vip等级
        author.member.update_vip_level(recharge_record)
        # 金币流水
        coin_transaction = m.CreditCoinTransaction.objects.create(
            type=m.CreditCoinTransaction.TYPE_RECHARGE,
            user_debit=author,
            amount=m.CreditCoinTransaction.get_coin_by_product_id(productid),
            remark='充值{}'.format(orderid),
            #     注意这里的remark会在下面的 get_recharge_coin_transactions 里面使用
        )
        # 金币充值奖励流水
        recharge_award_amount = m.CreditCoinTransaction.get_award_coin_by_product_id(productid,
                                                                                     m.RechargeRecord.objects.filter(
                                                                                         author=author,
                                                                                         payment_record__product_id=productid).count() <= 1)
        level_award_amount = 0
        vip_award_amount = 0
        if m.Option.get('level_rules') and m.Option.get('vip_rules'):
            level_rules = json.loads(m.Option.get('level_rules'))
            vip_rules = json.loads(m.Option.get('vip_rules'))
            # 等级储值返点
            if author.member.large_level > 1:
                level_award_amount = int(int(level_rules.get('level_more')[author.member.large_level - 2].get(
                    'rebate')) * m.CreditCoinTransaction.get_coin_by_product_id(productid) / 100)
            # vip等级储值返点
            if author.member.vip_level > 0:
                vip_award_amount = int(vip_rules[author.member.vip_level - 1].get(
                    'rebate') * m.CreditCoinTransaction.get_coin_by_product_id(productid) / 100)
        award_coin_transaction = m.CreditCoinTransaction.objects.create(
            type=m.CreditCoinTransaction.TYPE_RECHARGE,
            user_debit=author,
            amount=recharge_award_amount + level_award_amount + vip_award_amount,
            remark='充值奖励{}'.format(orderid),
            #     注意这里的remark会在下面的 get_recharge_coin_transactions 里面使用
        )
        return Response(data=dict(code='0', msg=''))

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['GET'])
    def get_total_recharge_this_month(self, request):
        qs = self.queryset
        now = datetime.now()
        first_day = datetime(now.year, now.month, 1)
        if now.month == 12:
            last_day = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        qs = qs.filter(
            author=self.request.user,
            date_created__gt=first_day,
            date_created__lt=last_day,
        )
        total = 0
        for recharge in qs:
            total += recharge.amount
        return Response(data=total)

    @list_route(methods=['GET'])
    def get_recharge_coin_transactions(self, request):
        author = self.request.user
        data = []
        for recharge_record in m.RechargeRecord.objects.filter(author=author):
            coin_transaction = m.CreditCoinTransaction.objects.filter(
                user_debit=author,
                remark='充值{}'.format(recharge_record.payment_record.out_trade_no),
            ).first()
            award_coin_transaction = m.CreditCoinTransaction.objects.filter(
                user_debit=author,
                remark='充值奖励{}'.format(recharge_record.payment_record.out_trade_no),
            ).first()
            data.append(dict(
                amount=recharge_record.amount,
                date_created=recharge_record.date_created,
                coin=coin_transaction.amount + award_coin_transaction.amount or 0,
            ))
        return Response(data=data)


class LoginRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.LoginRecord.objects.all()
    serializer_class = s.LoginRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)

    @list_route(methods=['GET'])
    def get_active_chart_data(self, request):
        """
        数据分析 - 活躍用戶
        :param request:
        :return:
        """
        time_begin = self.request.query_params.get('time_begin')
        time_end = self.request.query_params.get('time_end')
        if not time_begin or not time_end:
            return response_fail('請填寫完整的時間區間')
        begin = datetime.strptime(time_begin, '%Y-%m-%d')
        end = datetime.strptime(time_end, '%Y-%m-%d')
        duration = end - begin
        data = None
        labels = []
        amounts = []
        if duration.days < 31:
            for i in range(duration.days + 1):
                label_item = '{}月{}號'.format(
                    (begin + timedelta(days=i)).month, (begin + timedelta(days=i)).day)
                amount_item = m.LoginRecord.objects.filter(
                    date_login__gt=begin + timedelta(days=i),
                    date_login__lt=begin + timedelta(days=i + 1)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        elif 31 < duration.days < 62:
            for i in range(int(duration.days / 7)):
                label_item = '{}月{}號 - {}月{}號'.format(
                    (begin + timedelta(days=i * 7)).month,
                    (begin + timedelta(days=i * 7)).day,
                    (begin + timedelta(days=(i + 1) * 7)).month,
                    (begin + timedelta(days=(i + 1) * 7)).day,
                )
                amount_item = m.LoginRecord.objects.filter(
                    date_login__gt=begin + timedelta(days=i * 7),
                    date_login__lt=begin + timedelta(days=(i + 1) * 7)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
                if i == int(duration.days / 7) - 1 and duration.days % 7 > 0:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        (begin + timedelta(days=(i + 1) * 7)).month,
                        (begin + timedelta(days=(i + 1) * 7)).day,
                        end.month,
                        end.day,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=begin + timedelta(days=(i + 1) * 7),
                        date_login__lt=end + timedelta(days=1),
                    ).count()
                    labels.append(label_item)
                    amounts.append(amount_item)
        elif 62 < duration.days <= 366:
            for i in range(int(duration.days / 31) + 2):
                if i == 0 and begin.day != 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        begin.month,
                        begin.day,
                        1 if begin.month == 12 else begin.month + 1,
                        1,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=begin,
                        date_login__lt=datetime(begin.year + 1, 1, 1) if begin.month == 12 else datetime(
                            begin.year, begin.month + 1, 1),
                    ).count()
                elif i == int(duration.days / 31) + 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        1 if begin.month + i == 12 else (begin.month + i) % 12,
                        1,
                        end.month,
                        end.day,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                1) if begin.month + i > 12 else datetime(begin.year,
                                                                                         begin.month + i, 1),
                        date_login__lt=end + timedelta(days=1)
                    ).count()
                else:
                    label_item = '{}月1號 - {}月1號'.format(
                        begin.month + i if begin.month + i <= 12 else (begin.month + i) % 12,
                        begin.month + i + 1 if begin.month + i + 1 <= 12 else (begin.month + i + 1) % 12,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                1) if begin.month + i > 12 else datetime(
                            begin.year, begin.month + i, 1),
                        date_login__lt=datetime(begin.year + 1, (begin.month + i + 1) % 12,
                                                1) if begin.month + i + 1 > 12 else datetime(
                            begin.year, begin.month + i + 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        else:
            for i in range(int(duration.days / 365) + 1):
                label_item = '{}年'.format(begin.year + i)
                if i == 0:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=begin,
                        date_created__lt=datetime(begin.year + 1, 1, 1)
                    ).count()
                elif i == duration.days / 365:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=end,
                    ).count()
                else:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=datetime(begin.year + i + 1, 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        data = dict(
            labels=labels,
            amounts=amounts,
        )
        return Response(data=data)

    @list_route(methods=['GET'])
    def get_remain_chart_data(self, request):
        """
        数据分析 - 活躍用戶
        :param request:
        :return:
        """
        time_begin = self.request.query_params.get('time_begin')
        time_end = self.request.query_params.get('time_end')
        if not time_begin or not time_end:
            return response_fail('請填寫完整的時間區間')
        days = int(self.request.query_params.get('days'))
        print(days)
        begin = datetime.strptime(time_begin, '%Y-%m-%d')
        end = datetime.strptime(time_end, '%Y-%m-%d')
        duration = end - begin
        data = None
        labels = []
        amounts = []
        if duration.days < 31:
            for i in range(duration.days + 1):
                label_item = '{}月{}號'.format(
                    (begin + timedelta(days=i)).month, (begin + timedelta(days=i)).day)
                amount_item = m.LoginRecord.objects.filter(
                    date_login__gt=begin + timedelta(days=i),
                    date_login__lt=begin + timedelta(days=i + 1)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        elif 31 < duration.days < 62:
            for i in range(int(duration.days / 7)):
                label_item = '{}月{}號 - {}月{}號'.format(
                    (begin + timedelta(days=i * 7)).month,
                    (begin + timedelta(days=i * 7)).day,
                    (begin + timedelta(days=(i + 1) * 7)).month,
                    (begin + timedelta(days=(i + 1) * 7)).day,
                )
                amount_item = m.LoginRecord.objects.filter(
                    date_login__gt=begin + timedelta(days=i * 7),
                    date_login__lt=begin + timedelta(days=(i + 1) * 7)
                ).count()
                labels.append(label_item)
                amounts.append(amount_item)
                if i == int(duration.days / 7) - 1 and duration.days % 7 > 0:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        (begin + timedelta(days=(i + 1) * 7)).month,
                        (begin + timedelta(days=(i + 1) * 7)).day,
                        end.month,
                        end.day,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=begin + timedelta(days=(i + 1) * 7),
                        date_login__lt=end + timedelta(days=1),
                    ).count()
                    labels.append(label_item)
                    amounts.append(amount_item)
        elif 62 < duration.days <= 366:
            for i in range(int(duration.days / 31) + 2):
                if i == 0 and begin.day != 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        begin.month,
                        begin.day,
                        1 if begin.month == 12 else begin.month + 1,
                        1,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=begin,
                        date_login__lt=datetime(begin.year + 1, 1, 1) if begin.month == 12 else datetime(
                            begin.year, begin.month + 1, 1),
                    ).count()
                elif i == int(duration.days / 31) + 1:
                    label_item = '{}月{}號 - {}月{}號'.format(
                        1 if begin.month + i == 12 else (begin.month + i) % 12,
                        1,
                        end.month,
                        end.day,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                1) if begin.month + i > 12 else datetime(begin.year,
                                                                                         begin.month + i, 1),
                        date_login__lt=end + timedelta(days=1)
                    ).count()
                else:
                    label_item = '{}月1號 - {}月1號'.format(
                        begin.month + i if begin.month + i <= 12 else (begin.month + i) % 12,
                        begin.month + i + 1 if begin.month + i + 1 <= 12 else (begin.month + i + 1) % 12,
                    )
                    amount_item = m.LoginRecord.objects.filter(
                        date_login__gt=datetime(begin.year + 1, (begin.month + i) % 12,
                                                1) if begin.month + i > 12 else datetime(
                            begin.year, begin.month + i, 1),
                        date_login__lt=datetime(begin.year + 1, (begin.month + i + 1) % 12,
                                                1) if begin.month + i + 1 > 12 else datetime(
                            begin.year, begin.month + i + 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        else:
            for i in range(int(duration.days / 365) + 1):
                label_item = '{}年'.format(begin.year + i)
                if i == 0:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=begin,
                        date_created__lt=datetime(begin.year + 1, 1, 1)
                    ).count()
                elif i == duration.days / 365:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=end,
                    ).count()
                else:
                    amount_item = m.LoginRecord.objects.filter(
                        date_created__gt=datetime(begin.year + i, 1, 1),
                        date_created__lt=datetime(begin.year + i + 1, 1, 1),
                    ).count()
                labels.append(label_item)
                amounts.append(amount_item)
        data = dict(
            labels=labels,
            amounts=amounts,
        )
        return Response(data=data)


class PaymentRecordViewSet(viewsets.ModelViewSet):
    filter_fields = '__all__'
    queryset = m.PaymentRecord.objects.all()
    serializer_class = s.PaymentRecordSerializer
    ordering = ['-pk']

    def get_queryset(self):
        return interceptor_get_queryset_kw_field(self)
