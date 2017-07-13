import json


class WebIM:
    API_ROOT = 'https://console.tim.qq.com/v4/'

    appid = None
    identifier = None
    user_sig = None

    def __init__(self, appid, identifier='admin'):
        """
        初始化并登录某个账号
        :param appid:
        :param identifier: 指定的登录账号，admin 为管理员
        :return:
        """
        from .. import auth
        self.appid = appid
        self.identifier = identifier
        self.user_sig = auth.generate_sig(identifier, appid)

    def make_url(self, service_name, command):
        from random import randint
        return '{}{}/{}?sdkappid={}&identifier={}&usersig={}&random={}&contenttype=json'.format(
            self.API_ROOT,
            service_name,
            command,
            self.appid,
            self.identifier,
            self.user_sig,
            randint(0, 1 << 32),
        )

    def post(self, service_name, command, data):
        from urllib.request import urlopen
        # 返回格式
        # {
        #     "ActionStatus": "OK",
        #     "ErrorInfo": "",
        #     "ErrorCode": 0,
        #     // REST API其他应答内容
        # }
        url = self.make_url(service_name, command)
        # 支持直接传入对象，如果这样的话转成字符串
        if type(data) == dict:
            data = json.dumps(data)
        # 编码成 bytes
        if type(data) == str:
            data = data.encode()
        resp = urlopen(url, data)
        return json.loads(resp.read().decode())

    # ========
    # 应用功能
    # ========

    # 群组类型
    GROUP_TYPE_PUBLIC = 'Public'  # 公开群
    GROUP_TYPE_PRIVATE = 'Private'  # 私密群
    GROUP_TYPE_CHAT_ROOM = 'ChatRoom'  # 聊天室
    GROUP_TYPE_AV_CHAT_ROOM = 'AVChatRoom'  # 互动直播聊天室
    GROUP_TYPE_B_CHAT_ROOM = 'BChatRoom'  # 在线成员广播大群

    # 申请加群处理方式
    APPLY_JOIN_OPTION_FREE_ACCESS = 'FreeAccess'  # 自由加入
    APPLY_JOIN_OPTION_NEED_PERMISSION = 'NeedPermission'  # 需要验证
    APPLY_JOIN_OPTION_DISABLE_APPLY = 'DisableApply'  # 禁止加群

    def create_group(self, owner_account, name='New Group', type=GROUP_TYPE_PUBLIC,
                     group_id=None, introduction='', notification='', face_url=None,
                     max_member_count=0, apply_join_option=None,
                     app_defined_data=None, member_list=()):
        """ 创建群
        :param owner_account: 群主账号
        :param name: 群名称
        :param type: 群类型
        :param group_id: 自定义群组ID，缺省的话自动生成
        :param introduction: 群简介
        :param notification: 群公告
        :param face_url: 群头像URL
        :param max_member_count: 最大成员数量
        :param apply_join_option: 加群方式
        :param app_defined_data: 群组自定义字段（字典即可）
        :param member_list: 群成员列表 dict(Member_Account, Role, <dict>AppMemberDefinedData)
        :return:
        """
        data = dict(
            Owner_Account=owner_account,
            Type=type,
            Name=name,
            Introduction=introduction,
            Notification=notification,
        )
        # 自定义群组 ID
        if group_id:
            data['GroupId'] = group_id
        # 群头像
        if face_url:
            data['FaceUrl'] = face_url
        # 最大成员数量
        if max_member_count:
            data['MaxMemberCount'] = max_member_count
        if apply_join_option:
            data['ApplyJoinOption'] = apply_join_option
        if app_defined_data:
            data['AppDefinedData'] = list([dict(Key=k, Value=v) for k, v in app_defined_data.items()])
        # print(data)
        return self.post('group_open_http_svc', 'create_group', data)

    def add_group_member(self, group_id, member_list, silence: False):
        """ 添加群组成员
        https://www.qcloud.com/document/product/269/1621
        :param group_id: 自定义群组ID，缺省的话自动生成
        :param member_list: 群成员列表 dict(Member_Account, Role, <dict>AppMemberDefinedData)
        :param silence: 是否静默（不向会员发送通知）
        :return:
        """
        data = dict(
            GroupId=group_id,
            MemberList=member_list,
        )
        if silence:
            data['Silence'] = 1
        return self.post('group_open_http_svc', 'add_group_member', data)

    MSG_TYPE_TEXT = 'TIMTextElem'
    MSG_TYPE_LOCATION = 'TIMLocationElem'
    MSG_TYPE_FACE = 'TIMFaceElem'
    MSG_TYPE_CUSTOM = 'TIMCustomElem'
    MSG_TYPE_SOUND = 'TIMSoundElem'
    MSG_TYPE_IMAGE = 'TIMImageElem'
    MSG_TYPE_FILE = 'TIMFileElem'

    @classmethod
    def make_msg_elem(cls, msg_type, content):
        return dict(
            MsgType=msg_type,
            MsgContent=content,
        )

    @classmethod
    def make_msg_elem_text(cls, text):
        return cls.make_msg_elem(cls.MSG_TYPE_TEXT, dict(Text=text))

    @classmethod
    def make_msg_elem_location(cls, desc, latitude, longitude):
        return cls.make_msg_elem(cls.MSG_TYPE_LOCATION, dict(
            Desc=desc,
            Latitude=latitude,
            Longitude=longitude,
        ))

    @classmethod
    def make_msg_elem_face(cls, index, data):
        return cls.make_msg_elem(cls.MSG_TYPE_FACE, dict(Index=index, Data=data))

    @classmethod
    def make_msg_elem_custom(cls, data, desc, ext, sound):
        return cls.make_msg_elem(cls.MSG_TYPE_CUSTOM, dict(
            Data=data, Desc=desc, Ext=ext, Sound=sound
        ))

    @classmethod
    def make_msg_elem_sound(cls, uuid, size, second):
        return cls.make_msg_elem(cls.MSG_TYPE_SOUND, dict(
            UUID=uuid, Size=size, Second=second
        ))

    IMAGE_FORMAT_BMP = 1
    IMAGE_FORMAT_JPG = 2
    IMAGE_FORMAT_GIF = 3
    IMAGE_FORMAT_OTHER = 0

    @classmethod
    def make_msg_elem_image(cls, uuid, image_format, image_info_array):
        return cls.make_msg_elem(cls.MSG_TYPE_IMAGE, dict(
            UUID=uuid, ImageFormat=image_format, image_info_array=image_info_array
        ))

    @classmethod
    def make_msg_elem_file(cls, uuid, file_size, file_name):
        return cls.make_msg_elem(cls.MSG_TYPE_FILE, dict(
            UUID=uuid, FileSize=file_size, FileName=file_name
        ))

    MSG_PRIORITY_HIGH = 'High'
    MSG_PRIORITY_NORMAL = 'Normal'
    MSG_PRIORITY_LOW = 'Low'
    MSG_PRIORITY_LOWEST = 'Lowest'

    def send_group_msg(self, group_id, msg_body, from_account='admin', priority=MSG_PRIORITY_NORMAL):
        """ 在群组中发送普通消息
        https://www.qcloud.com/document/product/269/1629
        :param group_id:
        :param msg_body:
        :param from_account:
        :param priority:
        :return:
        """
        from random import randint
        data = dict(
            GroupId=group_id,
            Random=randint(0, 1 << 32),
            MsgBody=msg_body,
            FromAccount=from_account,
            MsgPriority=priority,
        )
        return self.post('group_open_http_svc', 'send_group_msg', data)
