# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-05 11:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20170628_1644'),
    ]

    operations = [
        migrations.AddField(
            model_name='live',
            name='paid',
            field=models.IntegerField(default=0, verbose_name='收費'),
        ),
        migrations.AlterField(
            model_name='livewatchlog',
            name='duration',
            field=models.IntegerField(default=0, help_text='單位（分鐘）', verbose_name='停留時長'),
        ),
    ]
