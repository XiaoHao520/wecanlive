# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-22 14:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_auto_20170821_1614'),
    ]

    operations = [
        migrations.AddField(
            model_name='activeevent',
            name='like_count',
            field=models.IntegerField(default=0, verbose_name='点赞数'),
        ),
    ]
