# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-04 00:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20170628_1644'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='member',
            name='date_ilive_sig_expire',
        ),
        migrations.RemoveField(
            model_name='member',
            name='ilive_sig',
        ),
        migrations.AlterField(
            model_name='livewatchlog',
            name='duration',
            field=models.IntegerField(default=0, help_text='單位（分鐘）', verbose_name='停留時長'),
        ),
    ]