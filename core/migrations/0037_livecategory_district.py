# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-09-12 11:48
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_live_end_scene_img'),
    ]

    operations = [
        migrations.AddField(
            model_name='livecategory',
            name='district',
            field=models.IntegerField(blank=True, null=True, verbose_name='区划编码'),
        ),
    ]