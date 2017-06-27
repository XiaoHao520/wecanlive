from django.test import TestCase
from core.models import *


class MemberTests(TestCase):
    def setUp(self):
        print('SETUP')

    def tearDown(self):
        print('TEAR DOWN')

    def test_user_follow(self):
        from django.contrib.auth.hashers import make_password
        amy = User.objects.create(
            username='amy',
            password=make_password('AABb1122')
        )
        bob = User.objects.create(
            username='bob',
            password=make_password('AABb1122')
        )
        amy_member = Member.objects.create(
            user=amy,
            mobile='13533808433',
        )
        amy_member.set_followed_by(bob, 'follow')
        self.assertTrue(
            UserMark.objects.filter(
                author=bob,
                content_type=ContentType.objects.get(
                    app_label='core',
                    model='Member',
                ),
                object_id=amy_member.pk,
                subject='follow'
            ).exists(),
            '用戶設置跟蹤狀態後沒有正确產生 UserMark 對象'
        )
        self.assertEqual(
            Member.get_objects_marked_by(bob, 'follow').first(),
            amy_member,
            'get_objects_marked_by 返回结果不正确'
        )
