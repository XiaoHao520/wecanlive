# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-09-29 15:12
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0049_liverecordlog'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='liverecordlog',
            name='live',
        ),
        migrations.AddField(
            model_name='liverecordlog',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='liverecordlogs_owned', to=settings.AUTH_USER_MODEL, verbose_name='作者'),
        ),
        migrations.AlterField(
            model_name='liverecordlog',
            name='channel_id',
            field=models.CharField(help_text='(channel_id)同stream_id', max_length=25, verbose_name='直播码'),
        ),
        migrations.AlterField(
            model_name='liverecordlog',
            name='stream_id',
            field=models.CharField(help_text='(stream_id)标志事件源于哪一条直播流', max_length=25, verbose_name='直播码'),
        ),
    ]
