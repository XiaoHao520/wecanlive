# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-12 15:46
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_live_end_scene_img'),
    ]

    operations = [
        migrations.AddField(
            model_name='familymissionachievement',
            name='experience_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='family_mission_achievement', to='core.ExperienceTransaction', verbose_name='奖励經驗记录'),
        ),
        migrations.AlterField(
            model_name='experiencetransaction',
            name='type',
            field=models.CharField(choices=[('SIGN', '登录'), ('SHARE', '分享'), ('RECEIVE', '收礼'), ('SEND', '送礼'), ('WATCH', '观看直播'), ('LIVE', '直播'), ('LIVE', '活动'), ('OTHER', '其他'), ('MISSION', '任務')], max_length=10, verbose_name='类型'),
        ),
        migrations.AlterField(
            model_name='familymissionachievement',
            name='badge_record',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='family_mission_achievement', to='core.BadgeRecord', verbose_name='奖励勋章记录'),
        ),
        migrations.AlterField(
            model_name='familymissionachievement',
            name='prize_star_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='family_mission_achievement', to='core.CreditStarTransaction', verbose_name='奖励星星流水记录'),
        ),
    ]
