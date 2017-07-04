import traceback
from rest_framework.utils import model_meta
from rest_framework import serializers
from rest_framework.compat import set_many
from drf_extra_fields.fields import Base64ImageField

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


class UserSerializer(serializers.ModelSerializer):
    # real_name = serializers.ReadOnlyField(source='real_name')
    # nickname = serializers.ReadOnlyField(source='nickname')
    # gender = serializers.ReadOnlyField(source='gender')

    # assistant = serializers.PrimaryKeyRelatedField(read_only=True)

    # assistant_nickname = serializers.ReadOnlyField(source='assistant.nickname')

    # member = serializers.PrimaryKeyRelatedField(read_only=True)

    member_nickname = serializers.ReadOnlyField(source='member.nickname')

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

    class Meta:
        model = m.User
        exclude = ['password', 'user_permissions']
        # fields = (
        #     'id', 'username', 'first_name', 'last_name',
        #     'email', 'is_superuser', 'is_staff', 'customer',
        # )


# class TagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = m.Tag
#         fields = '__all__'
class AudioSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.AudioModel
        fields = '__all__'


class ImageSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = m.ImageModel
        fields = '__all__'


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Bank
        fields = '__all__'


class BankAccountSerializer(serializers.ModelSerializer):
    bank_item = BankSerializer(
        source='bank',
        read_only=True,
    )

    class Meta:
        model = m.BankAccount
        fields = '__all__'


class UserDetailedSerializer(serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='member.nickname')
    gender = serializers.ReadOnlyField(source="member.gender")
    age = serializers.ReadOnlyField(source="member.age")
    constellation = serializers.ReadOnlyField(source="member.constellation")
    avatar_url = serializers.ReadOnlyField(source="member.avatar.image.url")
    signature = serializers.ReadOnlyField(source="member.signature")
    diamond_balance = serializers.ReadOnlyField(source='member.get_diamond_balance')
    coin_balance = serializers.ReadOnlyField(source='member.get_coin_balance')
    # 跟踪数量
    count_follow = serializers.ReadOnlyField(
        source='member.get_follow_count',
    )
    # 粉丝数量
    count_followed = serializers.ReadOnlyField(
        source='member.get_followed_count',
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


class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Menu
        fields = '__all__'


class GroupInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.GroupInfo
        fields = '__all__'


class GroupSerializer(AllowNestedWriteMixin,
                      serializers.ModelSerializer):
    info = GroupInfoSerializer(read_only=True)

    menus = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=m.Menu.objects.exclude(parent=None),
    )

    class Meta:
        model = m.Group
        fields = '__all__'


class MessageSerializer(AllowNestedWriteMixin,
                        serializers.ModelSerializer):
    author_item = UserSerializer(
        source='author',
        read_only=True,
    )

    avatar_url = serializers.ReadOnlyField(read_only=True)

    images_item = ImageSerializer(
        source='images',
        many=True,
        read_only=True,
    )

    class Meta:
        model = m.Message
        fields = '__all__'


class PaymentRecordSerializer(serializers.ModelSerializer):
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


class BroadcastSerializer(serializers.ModelSerializer):
    target_text = serializers.ReadOnlyField()

    class Meta:
        model = m.Broadcast
        fields = '__all__'


class AddressDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.AddressDistrict
        fields = '__all__'


# core
class InfomableSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.InformableModel
        fields = '__all__'


class MemberSerializer(serializers.ModelSerializer):
    avatar_url = serializers.ReadOnlyField(
        source='avatar.image.url',
    )

    avatar_item = ImageSerializer(
        source='avatar',
        read_only=True,
    )

    member_age = serializers.ReadOnlyField(
        source='get_age',
    )

    count_follow = serializers.ReadOnlyField(
        source='get_follow_count',
    )

    count_followed = serializers.ReadOnlyField(
        source='get_followed_count',
    )

    class Meta:
        model = m.Member
        # fields = '__all__'
        exclude = ['session_key', 'ilive_sig', 'date_ilive_sig_expire']


class RobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Robot
        fields = '__all__'


class CelebrityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CelebrityCategory
        fields = '__all__'


class CreditStarTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditStarTransaction
        fields = '__all__'


class CreditStarIndexTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditStarIndexTransaction
        fields = '__all__'


class CreditDiamondTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditDiamondTransaction
        fields = '__all__'


class CreditCoinTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditCoinTransaction
        fields = '__all__'


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Badge
        fields = '__all__'


class DailyCheckInLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.DailyCheckInLog
        fields = '__all__'


class Serializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditDiamondTransaction
        fields = '__all__'


class FamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Family
        fields = '__all__'


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.FamilyMember
        fields = '__all__'


class FamilyArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.FamilyArticle
        fields = '__all__'


class FamilyMissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.FamilyMission
        fields = '__all__'


class FamilyMissionAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.FamilyMissionAchievement
        fields = '__all__'


class LiveCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = m.LiveCategory
        fields = '__all__'


class LiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Live
        fields = '__all__'


class LiveBarrageSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.LiveBarrage
        fields = '__all__'


class LiveWatchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.LiveWatchLog
        fields = '__all__'


class ActiveEventSerializer(serializers.ModelSerializer):
    images_item = ImageSerializer(
        source='images',
        many=True,
        read_only=True,
    )

    class Meta:
        model = m.ActiveEvent
        fields = '__all__'


class PrizeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = m.PrizeCategory
        fields = '__all__'


class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Prize
        fields = '__all__'


class PrizeTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.PrizeTransition
        fields = '__all__'


class PrizeOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.PrizeOrder
        fields = '__all__'


class ExtraPrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ExtraPrize
        fields = '__all__'


class StatisticRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.StatisticRule
        fields = '__all__'


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Activity
        fields = '__all__'


class ActivityParticipationSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ActivityParticipation
        fields = '__all__'


class NotificationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Notifications
        fields = '__all__'


class VisitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.VisitLog
        fields = '__all__'


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Movie
        fields = '__all__'


class StarBoxSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.StarBox
        fields = '__all__'


class StarBoxRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.CreditDiamondTransaction
        fields = '__all__'


class RedBagRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.RedBagRecord
        fields = '__all__'


class StarMissionAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.StarMissionAchievement
        fields = '__all__'


class LevelOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.LevelOption
        fields = '__all__'


class InformSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Inform
        fields = '__all__'


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Feedback
        fields = '__all__'


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Banner
        fields = '__all__'


class SensitiveWordSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.SensitiveWord
        fields = '__all__'


class DiamondExchangeRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.DiamondExchangeRecord
        fields = '__all__'


class CommentSerializer(serializers.ModelSerializer):
    author_avatar = serializers.ReadOnlyField(
        source='author.member.avatar.image.url',
    )

    author_nickname = serializers.ReadOnlyField(
        source='author.member.nickname'
    )

    class Meta:
        model = m.Comment
        fields = '__all__'


class UserMarkSerializer(serializers.ModelSerializer):
    author_avatar = serializers.ReadOnlyField(
        source='author.member.avatar.image.url',
    )

    author_nickname = serializers.ReadOnlyField(
        source='author.member.nickname'
    )

    class Meta:
        model = m.UserMark
        fields = '__all__'


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Contact
        fields = '__all__'
