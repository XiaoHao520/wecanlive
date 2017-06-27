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

    def test_002_ilive_sig_generation(self):
        amy = User.objects.get(username='amy')
        self.assertEqual(len(amy.member.ilive_sig), 320, '生成的 ilive 签名 长度不正确')
        self.assertGreater(amy.member.date_ilive_sig_expire, datetime.now(), 'ilive 签名时间一创建就已经超时')
        # 自动刷新超时的时间
        old_sig = amy.member.ilive_sig
        amy.member.date_ilive_sig_expire = None
        amy.member.save()
        self.assertNotEqual(amy.member.ilive_sig, old_sig, '超时没有重新生成 Ilive_sig')
        self.assertGreater(amy.member.date_ilive_sig_expire, datetime.now(), 'ilive 重新生成的 sig 不在有效期')



