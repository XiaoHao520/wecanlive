# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-05 17:40
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_auto_20170804_1625'),
    ]

    operations = [
        migrations.AddField(
            model_name='familymissionachievement',
            name='badge_record',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.BadgeRecord', verbose_name='奖励勋章记录'),
        ),
        migrations.AddField(
            model_name='familymissionachievement',
            name='coin_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='family_mission_achievement', to='core.CreditCoinTransaction', verbose_name='奖励金币记录'),
        ),
        migrations.AddField(
            model_name='familymissionachievement',
            name='prize_star_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.CreditStarTransaction', verbose_name='奖励星星流水记录'),
        ),
        migrations.AddField(
            model_name='familymissionachievement',
            name='prize_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='family_mission_achievement', to='core.PrizeTransaction', verbose_name='獎勵礼物记录'),
        ),
    ]