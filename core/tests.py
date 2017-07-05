from django.test import TestCase
from core.models import *


class MemberTests(TestCase):
    def setUp(self):
        from django.contrib.auth.hashers import make_password
        amy = User.objects.create(username='amy', password=make_password('AABb1122'))
        Member.objects.create(user=amy, mobile='13533808433')
        bob = User.objects.create(username='bob', password=make_password('AABb1122'))
        Member.objects.create(user=bob, mobile='13533808432')

    def tearDown(self):
        pass

    def test_000_create_user(self):
        pass

    def test_001_user_follow(self):
        amy = User.objects.get(username='amy')
        bob = User.objects.get(username='bob')
        amy.member.set_followed_by(bob, 'follow')
        self.assertTrue(
            UserMark.objects.filter(
                author=bob,
                content_type=ContentType.objects.get(
                    app_label='core',
                    model='Member',
                ),
                object_id=amy.pk,
                subject='follow'
            ).exists(),
            '用戶設置跟蹤狀態後沒有正确產生 UserMark 對象'
        )
        self.assertEqual(
            Member.get_objects_marked_by(bob, 'follow').first(),
            amy.member,
            'get_objects_marked_by 返回结果不正确'
        )


