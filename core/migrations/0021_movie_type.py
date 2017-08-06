# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-28 16:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_badgerecord_date_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='type',
            field=models.CharField(blank=True, choices=[('MOVIE', '影片'), ('LIVE', '直播')], default='', max_length=20, verbose_name='類型'),
        ),
    ]
