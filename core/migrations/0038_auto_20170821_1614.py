# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-21 16:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_member_check_member_history'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='check_member_history',
            field=models.TextField(blank=True, help_text='当天内查看非好友会员的id', null=True, verbose_name='查看谁看过我列表记录'),
        ),
    ]