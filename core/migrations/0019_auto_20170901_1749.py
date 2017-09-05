# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-01 17:49
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_activityparticipation_prize_transaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='activityparticipation',
            name='star_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='activity_participation', to='core.CreditStarTransaction', verbose_name='元气奖励记录'),
        ),
        migrations.AlterField(
            model_name='creditstartransaction',
            name='type',
            field=models.CharField(choices=[('LIVE_GIFT', '直播赠送'), ('EARNING', '任務獲得'), ('ADMIN', '後臺補償'), ('DAILY', '签到获得'), ('ACTIVITY', '活动获得')], max_length=20, verbose_name='流水类型'),
        ),
    ]