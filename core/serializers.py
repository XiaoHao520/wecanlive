import traceback
from rest_framework.utils import model_meta
from rest_framework import serializers
from rest_framework.compat import set_many
from drf_extra_fields.fields import Base64ImageField
from drf_queryfields import QueryFieldsMixin

from . import models as m


class AllowNestedWriteMixin:
    """
    DRF 为了各种原因的考虑，硬是把 Many2many 的写入给掐掉了。
    说是如果要用 nested 写入，自己写一个 create/update 方法。
    我发现怎么写都和 DRF 的源码一尻样，所以还不如直接用回框架的源码。
    只需要注释掉 raise_errors_on_nested_writes 一行就可以用的。
    这里用一个 Tricky 制造了一个 Mixin，如果需要 nested write 的话，
    在继承 ModelSerializer 的基础上，再继承这个 Mixin 即可。
    """

    def create(self, validated_data):
        """
        We have a bit of extra checking around this in order to provide
        descriptive messages when something goes wrong, but this method is
        essentially just:

            return ExampleModel.objects.create(**validated_data)

        If there are many to many fields present on the instance then they
        cannot be set until the model is instantiated, in which case the
        implementation is like so:

            example_relationship = validated_data.pop('example_relationship')
            instance = ExampleModel.objects.create(**validated_data)
            instance.example_relationship = example_relationship
            return instance

        The default implementation also does not handle nested relationships.
        If you want to support writable nested relationships you'll need
        to write an explicit `.create()` method.
        """

        ModelClass = self.Meta.model

        # Remove many-to-many relationships from validated_data.
        # They are not valid arguments to the default `.create()` method,
        # as they require that the instance has already been saved.
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            instance = ModelClass.objects.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception was:\n %s' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    tb
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                set_many(instance, field_name, value)

        return instance

    def update(self, instance, validated_data):
        info = model_meta.get_field_info(instance)

        # Simply set each attribute on the instance, and then save it.
        # Note that unlike `.create()` we don't need to treat many-to-many
        # relationships as being a special case. During updates we already
        # have an instance pk for the relationships to be associated with.
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                set_many(instance, attr, value)
            else:
                setattr(instance, attr, value)
        instance.save()

        return instance


class UserOwndedMixinSerializer(serializers.Serializer):
    member_name = serializers.ReadOnlyField(
        source='author.member.nickname')

    shop_name = serializers.ReadOnlyField(
        source='author.shop.name')


class UserVotableMixinSerializer(serializers.Serializer):
    count_upvote = serializers.ReadOnlyField()
    count_downvote = serializers.ReadOnlyField()
    myvote = serializers.ReadOnlyField()


class UserSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    # real_name = serializers.ReadOnlyField(source='real_name')
    # nickname = serializers.ReadOnlyField(source='nickname')
    # gender = serializers.ReadOnlyField(source='gender')

    # assistant = serializers.PrimaryKeyRelatedField(read_only=True)

    # assistant_nickname = serializers.ReadOnlyField(source='assistant.nickname')

    # member = serializers.PrimaryKeyRelatedField(read_only=True)

    member_nickname = serializers.ReadOnlyField(source='member.nickname')

    member_avatar = serializers.ReadOnlyField(source='member.avatar.image.url')

    # personal_credit_score = serializers.ReadOnlyField(
    #     source='get_personal_credit_score',
    # )

    # social_credit_score = serializers.ReadOnlyField(
    #     source='get_social_credit_score',
    # )

    # shop_credit_score = serializers.ReadOnlyField(
    #     source='get_shop_credit_score',
    # )

    # contact_from_me = serializers.BooleanField(read_only=True)

    # contact_to_me = serializers.BooleanField(read_only=True)

    member_level = serializers.ReadOnlyField(source='member.get_level')

    member_vip_level = serializers.ReadOnlyField(source='member.get_vip_level')

    group_names = serializers.ReadOnlyField()

    class Meta:
        model = m.User
        exclude = ['password', 'user_permissions']
        # fields = (
        #     'id', 'username', 'first_name', 'last_name',
        #     'email', 'is_superuser', 'is_staff', 'customer',
        # )


# class TagSerializer(QueryFieldsMixin, serializers.ModelSerializer):
#     class Meta:
#         model = m.Tag
#         fields = '__all__'


class OptionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Option
        fields = '__all__'


class AudioSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.AudioModel
        fields = '__all__'


class ImageSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = m.ImageModel
        fields = '__all__'


class BankSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Bank
        fields = '__all__'


class AccountTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    user_credit_nickname = serializers.ReadOnlyField(
        source='user_credit.member.nickname',
    )

    user_credit_mobile = serializers.ReadOnlyField(
        source='user_credit.member.mobile',
    )

    user_debit_nickname = serializers.ReadOnlyField(
        source='user_debit.member.nickname',
    )

    user_debit_mobile = serializers.ReadOnlyField(
        source='user_debit.member.mobile',
    )

    # nickname = serializers.ReadOnlyField(
    #     source='member.nickname',
    # )
    #
    # mobile = serializers.ReadOnlyField(
    #     source='member.mobile',
    # )
    #
    # platform = serializers.ReadOnlyField(
    #     source='payment_platform',
    # )
    #
    # out_trade_no = serializers.ReadOnlyField(
    #     source='payment_out_trade_no',
    # )

    nickname = serializers.ReadOnlyField(
        source='account_transaction_member.nickname',
    )

    mobile = serializers.ReadOnlyField(
        source='account_transaction_member.mobile',
    )

    platform = serializers.ReadOnlyField(
        source='account_transaction_payment_platform',
    )

    out_trade_no = serializers.ReadOnlyField(
        source='account_transaction_payment_out_trade_no',
    )

    class Meta:
        model = m.AccountTransaction
        fields = '__all__'


class BankAccountSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    bank_item = BankSerializer(
        source='bank',
        read_only=True,
    )

    class Meta:
        model = m.BankAccount
        fields = '__all__'


class RechargeRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_item = UserSerializer(
        source='author',
        read_only=True,
    )

    class Meta:
        model = m.RechargeRecord
        fields = '__all__'


class UserDetailedSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='member.nickname')
    gender = serializers.ReadOnlyField(source="member.gender")
    age = serializers.ReadOnlyField(source="member.age")
    constellation = serializers.ReadOnlyField(source="member.constellation")
    avatar_url = serializers.ReadOnlyField(source="member.avatar.image.url")
    signature = serializers.ReadOnlyField(source="member.signature")

    diamond_balance = serializers.ReadOnlyField(source='member.get_diamond_balance')
    coin_balance = serializers.ReadOnlyField(source='member.get_coin_balance')
    star_balance = serializers.ReadOnlyField(source='member.get_star_balance')
    star_index_sender_balance = serializers.ReadOnlyField(source='member.get_star_index_sender_balance')
    star_index_receiver_balance = serializers.ReadOnlyField(source='member.get_star_index_receiver_balance')

    member_level = serializers.ReadOnlyField(source='member.get_level')
    member_experience = serializers.ReadOnlyField(source='member.total_experience')
    member_vip_level = serializers.ReadOnlyField(source='member.vip_level')

    # 跟踪数量
    count_follow = serializers.ReadOnlyField(
        source='member.get_follow_count',
    )
    # 粉丝数量
    count_followed = serializers.ReadOnlyField(
        source='member.get_followed_count',
    )

    # 是否签到
    is_checkin_daily = serializers.ReadOnlyField(
        source='member.is_checkin_daily',
    )

    # institution_validation_status = serializers.ReadOnlyField()

    # institution_validations = InstitutionValidationSerializer(
    #     source='institutionvalidations_owned',
    #     read_only=True,
    #     many=True,
    # )

    # entity_store_validation_status = serializers.ReadOnlyField()

    # entity_store_validations = EntityStoreValidationSerializer(
    #     source='entitystorevalidations_owned',
    #     read_only=True,
    #     many=True,
    # )

    # assistant = serializers.PrimaryKeyRelatedField(read_only=True)

    # amount_balance = serializers.ReadOnlyField(source='get_balance')

    # amount_credit = serializers.ReadOnlyField(source='get_credit')

    # amount_advert_credit = serializers.ReadOnlyField(source='get_advert_credit')

    # amount_commission = serializers.ReadOnlyField(source='get_commission')

    # amount_purchase = serializers.ReadOnlyField(source='get_amount_purchase')

    # withdraw_quota = serializers.ReadOnlyField(source='get_withdraw_quota')

    # personal_validation_status_text = \
    #     serializers.ReadOnlyField(source='get_personal_validation_status_text')

    # institution_validation_status_text = \
    #     serializers.ReadOnlyField(source='get_institution_validation_status_text')

    # entity_store_validation_status_text = \
    #     serializers.ReadOnlyField(source='get_entity_store_validation_status_text')


    class Meta:
        model = m.User
        exclude = ['password', 'user_permissions']


class WithdrawRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(
        source='author.member.nickname',
    )

    mobile = serializers.ReadOnlyField(
        source='author.member.mobile',
    )

    account = serializers.ReadOnlyField(
        source='bank_account.number',
    )

    class Meta:
        model = m.WithdrawRecord
        fields = '__all__'


class MenuSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Menu
        fields = '__all__'


class GroupInfoSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.GroupInfo
        fields = '__all__'


class GroupSerializer(AllowNestedWriteMixin,
                      QueryFieldsMixin, serializers.ModelSerializer):
    info = GroupInfoSerializer(read_only=True)

    menus = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=m.Menu.objects.exclude(parent=None),
    )

    class Meta:
        model = m.Group
        fields = '__all__'


class MessageSerializer(AllowNestedWriteMixin,
                        QueryFieldsMixin, serializers.ModelSerializer):
    # author_item = UserSerializer(
    #     source='author',
    #     read_only=True,
    # )

    avatar_url = serializers.ReadOnlyField(source='sender.member.avatar.image.url')

    images_item = ImageSerializer(
        source='images',
        many=True,
        read_only=True,
    )

    families = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=m.Family.objects.all(),
        required=False,
    )

    class Meta:
        model = m.Message
        fields = '__all__'


class PaymentRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    # payment_url = serializers.ReadOnlyField(source='get_payment_url')

    # recharge_record_id = serializers.PrimaryKeyRelatedField(
    #     source='recharge_record',
    #     queryset=m.RechargeRecord.objects.all(),
    # )

    # advert_recharge_record_id = serializers.PrimaryKeyRelatedField(
    #     source='advert_recharge_record',
    #     queryset=m.AdvertRechargeRecord.objects.all(),
    # )

    # order_id = serializers.PrimaryKeyRelatedField(
    #     source='order',
    #     queryset=m.CompetitionEntry.objects.all(),
    # )

    author_item = UserSerializer(
        source='author',
        read_only=True,
    )

    class Meta:
        model = m.PaymentRecord
        fields = '__all__'


class BroadcastSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    target_text = serializers.ReadOnlyField()

    class Meta:
        model = m.Broadcast
        fields = '__all__'


class AddressDistrictSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.AddressDistrict
        fields = '__all__'


# core
class InfomableSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.InformableModel
        fields = '__all__'


class MemberSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=m.User.objects.all(), )
    avatar_url = serializers.ReadOnlyField(source='avatar.image.url', )
    avatar_item = ImageSerializer(source='avatar', read_only=True)
    member_age = serializers.ReadOnlyField(source='get_age')
    count_follow = serializers.ReadOnlyField(source='get_follow_count')
    count_followed = serializers.ReadOnlyField(source='get_followed_count')
    count_friend = serializers.ReadOnlyField(source='get_friend_count')
    count_live = serializers.ReadOnlyField(source='get_live_count')
    last_live_end = serializers.ReadOnlyField(source='get_last_live_end')
    is_following = serializers.BooleanField(source='is_followed_by_current_user', read_only=True)

    # following_start_date = serializers.ReadOnlyField(source='get_following_start_date')
    # age = serializers.ReadOnlyField(source='get_age')

    credit_diamond = serializers.ReadOnlyField()
    debit_diamond = serializers.ReadOnlyField()
    # debit_star_index = serializers.ReadOnlyField()

    diamond_balance = serializers.ReadOnlyField(source='get_diamond_balance')
    coin_balance = serializers.ReadOnlyField(source='get_coin_balance')
    star_balance = serializers.ReadOnlyField(source='get_star_balance')
    star_index_sender_balance = serializers.ReadOnlyField(source='get_star_index_sender_balance')
    star_index_receiver_balance = serializers.ReadOnlyField(source='get_star_index_receiver_balance')

    level = serializers.ReadOnlyField(source='get_level')

    # vip_level = serializers.ReadOnlyField(source='get_vip_level')

    is_living = serializers.ReadOnlyField()

    contact_form_me = serializers.BooleanField(read_only=True)

    contact_to_me = serializers.BooleanField(read_only=True)

    first_live_date = serializers.ReadOnlyField(source='get_first_live_date')

    username = serializers.ReadOnlyField(source='user.username')

    is_not_disturb = serializers.ReadOnlyField()

    is_blacklist = serializers.ReadOnlyField()

    class Meta:
        model = m.Member
        # fields = '__all__'
        exclude = ['session_key', 'tencent_sig', 'tencent_sig_expire']


class RobotSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=m.User.objects.all(),
    )

    member_item = MemberSerializer(
        source='user.member',
        read_only=True,
    )

    avatar_item = ImageSerializer(
        source='user.member.avatar',
        read_only=True,
    )

    user_avatar = serializers.ReadOnlyField(
        source='user.member.avatar.image.url',
    )

    user_id = serializers.ReadOnlyField(
        source='user.id',
    )

    user_nickname = serializers.ReadOnlyField(
        source='user.member.nickname',
    )

    user_gender = serializers.ReadOnlyField(
        source='user.member.gender',
    )

    age = serializers.ReadOnlyField(
        source='user.member.get_age',
    )

    user_constellation = serializers.ReadOnlyField(
        source='user.member.constellation',
    )

    class Meta:
        model = m.Robot
        fields = '__all__'


class CelebrityCategorySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    leader_nickname = serializers.ReadOnlyField(source='leader.member.nickname')
    leader_mobile = serializers.ReadOnlyField(source='leader.member.mobile')

    category = serializers.ReadOnlyField(source='get_category')

    leader_avatar = serializers.ReadOnlyField(source='leader.member.avatar.image.url')

    class Meta:
        model = m.CelebrityCategory
        fields = '__all__'


class CreditStarTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditStarTransaction
        fields = '__all__'


class CreditStarIndexReceiverTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditStarIndexReceiverTransaction
        fields = '__all__'


class CreditStarIndexSenderTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditStarIndexSenderTransaction
        fields = '__all__'


class CreditDiamondTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditDiamondTransaction
        fields = '__all__'


class CreditCoinTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditCoinTransaction
        fields = '__all__'


class BadgeSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    icon_item = ImageSerializer(
        source='icon',
        read_only=True,
    )

    class Meta:
        model = m.Badge
        fields = '__all__'


class BadgeRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    badge_name = serializers.ReadOnlyField(
        source='badge.name',
    )

    icon_url = serializers.ImageField(
        source='badge.icon.image',
        read_only=True,
    )

    class Meta:
        model = m.BadgeRecord
        fields = '__all__'


class DailyCheckInLogSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    coin_amount = serializers.ReadOnlyField(source='coin_transaction.amount')

    star_amount = serializers.ReadOnlyField(source='prize_star_transaction.amount')

    class Meta:
        model = m.DailyCheckInLog
        fields = '__all__'


class Serializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.CreditDiamondTransaction
        fields = '__all__'


class FamilySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    logo_item = ImageSerializer(
        source='logo',
        read_only=True,
    )

    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    count_admin = serializers.ReadOnlyField(source='get_count_admin')

    count_family_member = serializers.ReadOnlyField(source='get_count_family_member')

    count_family_mission = serializers.ReadOnlyField(source='get_count_family_mission')

    count_family_article = serializers.ReadOnlyField(source='get_count_family_article')

    family_mission_cd = serializers.ReadOnlyField(source='get_family_mission_cd')

    class Meta:
        model = m.Family
        fields = '__all__'


class FamilyMemberSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField(source='author.is_active')

    author_avatar = serializers.ReadOnlyField(source='author.member.avatar.image.url')

    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')

    author_age = serializers.ReadOnlyField(source='author.member.age')

    author_gender = serializers.ReadOnlyField(source='author.member.gender')

    author_constellation = serializers.ReadOnlyField(source='author.member.constellation')

    watch_master_live_duration = serializers.ReadOnlyField()

    watch_master_live_prize = serializers.ReadOnlyField()

    class Meta:
        model = m.FamilyMember
        fields = '__all__'


class FamilyArticleSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')

    author_role = serializers.ReadOnlyField(source='get_author_role')

    class Meta:
        model = m.FamilyArticle
        fields = '__all__'


class FamilyMissionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')

    logo_item = ImageSerializer(
        source='logo',
        read_only=True,
    )

    is_end = serializers.ReadOnlyField()

    is_begin = serializers.ReadOnlyField()

    class Meta:
        model = m.FamilyMission
        fields = '__all__'


class FamilyMissionAchievementSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.FamilyMissionAchievement
        fields = '__all__'


class LiveCategorySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.LiveCategory
        fields = '__all__'


class LiveSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    category = serializers.ReadOnlyField(source='category.name')
    author_id = serializers.ReadOnlyField(source='author.id')
    nickname = serializers.ReadOnlyField(source='author.member.nickname')
    mobile = serializers.ReadOnlyField(source='author.member.mobile')
    author_avatar = serializers.ReadOnlyField(source='author.member.avatar.image.url')
    gender = serializers.ReadOnlyField(source='author.member.gender')
    constellation = serializers.ReadOnlyField(source='author.member.constellation')
    signature = serializers.ReadOnlyField(source='author.member.signature')
    age = serializers.ReadOnlyField(source='author.member.age')
    author_is_following = serializers.ReadOnlyField(
        source='author.member.is_followed_by_current_user',
        read_only=True,
    )

    count_comment = serializers.ReadOnlyField(source='get_comment_count')
    count_view = serializers.ReadOnlyField(source='get_view_count')
    count_prize = serializers.ReadOnlyField(source='get_prize_count')
    count_like = serializers.ReadOnlyField(source='get_like_count')

    # 主播粉丝数
    count_following_author = serializers.ReadOnlyField(source='author.member.get_followed_count')

    # 主播追踪数
    count_author_followed = serializers.ReadOnlyField(source='author.member.get_follow_count')
    count_author_diamond = serializers.ReadOnlyField(source='author.member.diamond_count')

    count_live_diamond = serializers.ReadOnlyField(source='get_live_diamond')
    count_live_receiver_star = serializers.ReadOnlyField(source='get_live_receiver_star')

    duration = serializers.ReadOnlyField(source='get_duration')
    live_status = serializers.ReadOnlyField(source='get_live_status')

    is_following = serializers.BooleanField(
        source='is_followed_by_current_user',
        read_only=True,
    )

    push_url = serializers.ReadOnlyField(source='get_push_url')
    play_url = serializers.ReadOnlyField(source='get_play_url')

    end_scene_img_url = serializers.ReadOnlyField(source='end_scene_img.image.url')

    class Meta:
        model = m.Live
        exclude = ['comments', 'informs']


class LiveBarrageSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_avatar_url = serializers.URLField(
        source='author.member.avatar.image.url',
        read_only=True,
    )

    author_nickname = serializers.ReadOnlyField(
        source='author.member.nickname'
    )

    author_level = serializers.ReadOnlyField(
        source='author.member.get_level'
    )

    author_vip_level = serializers.ReadOnlyField(
        source='author.member.get_vip_level'
    )

    class Meta:
        model = m.LiveBarrage
        fields = '__all__'
        ordering = ['-pk']


class LiveWatchLogSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    user_id = serializers.ReadOnlyField(
        source='author.id',
    )

    nickname = serializers.ReadOnlyField(
        source='author.member.nickname',
    )

    mobile = serializers.ReadOnlyField(
        source='author.member.mobile',
    )

    gender = serializers.ReadOnlyField(
        source='author.member.gender',
    )

    member_age = serializers.ReadOnlyField(
        source='author.member.get_age',
    )

    count_comment = serializers.ReadOnlyField(
        source='get_comment_count',
    )

    live_total_duration = serializers.ReadOnlyField(
        source='author.member.get_live_total_duration',
    )

    duration = serializers.ReadOnlyField(
        source='get_duration',
    )

    expense = serializers.ReadOnlyField(
        source='get_total_prize',
    )

    author_avatar_url = serializers.ImageField(
        source='author.member.avatar.image',
    )

    # watch_mission_count = serializers.ReadOnlyField(
    #     source='get_watch_mission_count',
    # )
    #
    # today_watch_mission_count = serializers.ReadOnlyField(
    #     source='author.member.get_today_watch_mission_count',
    # )
    #
    # information_mission_count = serializers.ReadOnlyField(
    #     source='author.member.get_information_mission_count'
    # )

    class Meta:
        model = m.LiveWatchLog
        fields = '__all__'


class ActiveEventSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    images_item = ImageSerializer(
        source='images',
        many=True,
        read_only=True,
    )

    preview = ImageSerializer(
        source='get_preview',
        read_only=True,
    )

    count_comment = serializers.ReadOnlyField(
        source='get_comment_count',
    )

    count_like = serializers.ReadOnlyField(
        source='get_like_count',
    )

    avatar_url = serializers.ReadOnlyField(
        source='author.member.avatar.image.url',
    )

    nickname = serializers.ReadOnlyField(
        source='author.member.nickname',
    )

    mobile = serializers.ReadOnlyField(
        source='author.member.mobile',
    )

    gender = serializers.ReadOnlyField(
        source='author.member.gender',
    )

    age = serializers.ReadOnlyField(
        source='author.member.age',
    )

    constellation = serializers.ReadOnlyField(
        source='author.member.constellation',
    )

    author_is_following = serializers.ReadOnlyField(
        source='author.member.is_followed_by_current_user',
    )

    is_like = serializers.ReadOnlyField(
        source='is_liked_by_current_user'
    )

    author_level = serializers.ReadOnlyField(
        source='author.member.get_level'
    )

    author_vip_level = serializers.ReadOnlyField(
        source='author.member.get_vip_level'
    )

    class Meta:
        model = m.ActiveEvent
        fields = '__all__'


class PrizeCategorySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    count_prize = serializers.ReadOnlyField(
        source='get_count_prize',
    )

    class Meta:
        model = m.PrizeCategory
        fields = '__all__'


class PrizeSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    icon_item = ImageSerializer(
        source='icon',
        read_only=True,
    )

    category_name = serializers.ReadOnlyField(
        source='category.name',
    )

    stickers_item = ImageSerializer(
        source='stickers',
        many=True,
        read_only=True,
    )

    marquee_image_item = ImageSerializer(
        source='marquee_image',
        read_only=True,
    )

    class Meta:
        model = m.Prize
        fields = '__all__'


class PrizeTransactionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    prize_name = serializers.ReadOnlyField(
        source='prize.name',
    )
    prize_image = serializers.ReadOnlyField(
        source='prize.icon.image.url',
    )

    class Meta:
        model = m.PrizeTransaction
        fields = '__all__'


class PrizeOrderSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_mobile = serializers.ReadOnlyField(
        source='author.member.mobile',
    )

    author_nickname = serializers.ReadOnlyField(
        source='author.member.nickname',
    )

    receiver_mobile = serializers.ReadOnlyField(
        source='receiver_prize_transaction.user_debit.member.mobile',
    )

    receiver_nickname = serializers.ReadOnlyField(
        source='receiver_prize_transaction.user_debit.member.nickname',
    )

    prize_name = serializers.ReadOnlyField(
        source='prize.name',
    )

    prize_category = serializers.ReadOnlyField(
        source='prize.category.name',
    )

    prize_marquee_url = serializers.ImageField(
        source='prize.marquee_image.image',
        read_only=True,
    )

    prize_marquee_size = serializers.ReadOnlyField(
        source='prize.marquee_size'
    )

    prize_price = serializers.ReadOnlyField(
        source='prize.price',
    )

    prize_transaction_item = PrizeTransactionSerializer(
        source='prize_transaction',
        read_only=True,
    )

    prize_transaction_amount = serializers.ReadOnlyField(
        source='sender_prize_transaction.amount',
    )

    # user_credit = serializers.ReadOnlyField(
    #     source='prize_transaction.user_credit.member.mobile',
    # )
    #
    # user_credit_nickname = serializers.ReadOnlyField(
    #     source='prize_transaction.user_credit.member.nickname',
    # )

    live_id = serializers.ReadOnlyField(
        source='live_watch_log.live.id',
    )

    live_author_id = serializers.ReadOnlyField(
        source='live_watch_log.live.author.id',
    )

    live_author_mobile = serializers.ReadOnlyField(
        source='live_watch_log.live.author.member.mobile',
    )

    live_author_nickname = serializers.ReadOnlyField(
        source='live_watch_log.live.author.member.nickname',
    )

    class Meta:
        model = m.PrizeOrder
        fields = '__all__'


class ExtraPrizeSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    prize_category_name = serializers.ReadOnlyField(
        source='prize_category.name',
    )

    wallpaper_url = serializers.ReadOnlyField(source="wallpaper.image.url")

    wallpaper_item = ImageSerializer(
        source='wallpaper',
        read_only=True,
    )

    class Meta:
        model = m.ExtraPrize
        fields = '__all__'


class StatisticRuleSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.StatisticRule
        fields = '__all__'


class ActivitySerializer(QueryFieldsMixin, serializers.ModelSerializer):
    thumbnail_item = ImageSerializer(
        source='thumbnail',
        read_only=True,
    )

    thumbnail_url = serializers.URLField(
        source='thumbnail.image.url',
        read_only=True,
    )

    vote_way = serializers.ReadOnlyField()

    vote_count_award = serializers.ReadOnlyField()

    status = serializers.ReadOnlyField()

    watch_min_watch = serializers.ReadOnlyField()

    watch_min_duration = serializers.ReadOnlyField()

    draw_condition_code = serializers.ReadOnlyField()

    draw_condition_value = serializers.ReadOnlyField()

    award_way = serializers.ReadOnlyField()

    date_end_countdown = serializers.ReadOnlyField()

    draw_activity_award = serializers.ReadOnlyField()

    class Meta:
        model = m.Activity
        fields = '__all__'


class ActivityPageSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    banner_item = ImageSerializer(
        source='banner',
        read_only=True,
    )

    activity_type = serializers.ReadOnlyField(source='activity.type')

    class Meta:
        model = m.ActivityPage
        fields = '__all__'


class ActivityParticipationSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.ActivityParticipation
        fields = '__all__'


class NotificationsSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Notifications
        fields = '__all__'


class VisitLogSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_avatar = serializers.ReadOnlyField(source='author.member.avatar.image.url')
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')
    author_gender = serializers.ReadOnlyField(source='author.member.gender')
    author_age = serializers.ReadOnlyField(source='author.member.age')
    author_constellation = serializers.ReadOnlyField(source='author.member.constellation')
    author_signature = serializers.ReadOnlyField(source='author.member.signature')

    contact_form_me = serializers.ReadOnlyField(source='author.member.contact_form_me')

    contact_to_me = serializers.ReadOnlyField(source='author.member.contact_to_me')

    # todo 距离 时间
    time_ago = serializers.ReadOnlyField()

    class Meta:
        model = m.VisitLog
        fields = '__all__'


class MovieSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    thumbnail_item = ImageSerializer(
        source='thumbnail',
        read_only=True,
    )

    class Meta:
        model = m.Movie
        fields = '__all__'


class StarBoxSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.StarBox
        fields = '__all__'


class StarBoxRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    coin_amount = serializers.ReadOnlyField(source="coin_transaction.amount")
    diamond_amount = serializers.ReadOnlyField(source="diamond_transaction.amount")
    prize_name = serializers.ReadOnlyField(source="prize_transaction.prize.name")
    prize_amount = serializers.ReadOnlyField(source="prize_transaction.amount")
    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    class Meta:
        model = m.StarBoxRecord
        fields = '__all__'


class RedBagRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.RedBagRecord
        fields = '__all__'


class StarMissionAchievementSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.StarMissionAchievement
        fields = '__all__'


class LevelOptionSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.LevelOption
        fields = '__all__'


class InformSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')

    accused_person = serializers.ReadOnlyField()

    accused_object_info = serializers.ReadOnlyField()

    class Meta:
        model = m.Inform
        fields = '__all__'


class FeedbackSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Feedback
        fields = '__all__'


class BannerSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    image_url = serializers.ReadOnlyField(
        source='image.image.url',
    )

    image_item = ImageSerializer(
        source='image',
        read_only=True,
    )

    class Meta:
        model = m.Banner
        fields = '__all__'


class SensitiveWordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.SensitiveWord
        fields = '__all__'


class DiamondExchangeRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.DiamondExchangeRecord
        fields = '__all__'


class CommentSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_avatar = serializers.ReadOnlyField(
        source='author.member.avatar.image.url',
    )

    nickname = serializers.ReadOnlyField(
        source='author.member.nickname',
    )

    mobile = serializers.ReadOnlyField(
        source='author.member.mobile',
    )

    watch_status = serializers.ReadOnlyField(
        source='comment_watch_status',
    )

    activeevent_img = serializers.ReadOnlyField(
        source='get_activeevent_img'
    )

    class Meta:
        model = m.Comment
        fields = '__all__'


class UserMarkSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_avatar = serializers.ReadOnlyField(
        source='author.member.avatar.image.url',
    )

    author_nickname = serializers.ReadOnlyField(
        source='author.member.nickname'
    )

    activeevent_img = serializers.ReadOnlyField(
        source='get_activeevent_img'
    )

    is_following = serializers.BooleanField(source='author.member.is_followed_by_current_user', read_only=True)

    class Meta:
        model = m.UserMark
        fields = '__all__'


class ContactSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.Contact
        fields = '__all__'


class RankRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_nickname = serializers.ReadOnlyField(source='author.member.nickname')

    author_mobile = serializers.ReadOnlyField(source='author.member.mobile')

    gender = serializers.ReadOnlyField(source='author.member.gender')

    age = serializers.ReadOnlyField(source='author.member.age')

    constellation = serializers.ReadOnlyField(source='author.member.constellation')

    author_level = serializers.ReadOnlyField(source='author.member.get_level')

    author_vip_level = serializers.ReadOnlyField(source='author.member.get_vip_level')

    author_avatar = serializers.ReadOnlyField(source='author.member.avatar.image.url')

    is_following = serializers.BooleanField(source='author.member.is_followed_by_current_user', read_only=True)

    class Meta:
        model = m.RankRecord
        fields = '__all__'


class AdminLogSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.first_name')

    author_groups = serializers.ReadOnlyField(source='author.group_names')

    author_account = serializers.ReadOnlyField(source='author.username')

    target_type = serializers.ReadOnlyField(source='target_type.name')

    class Meta:
        model = m.AdminLog
        fields = '__all__'


class LoginRecordSerializer(QueryFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = m.LoginRecord
        fields = '__all__'
