# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-24 14:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_merge_20170823_1026'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='content',
            field=models.TextField(blank=True, default='', verbose_name='内容'),
        ),
    ]
