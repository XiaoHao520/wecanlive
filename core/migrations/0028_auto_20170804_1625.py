# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-04 16:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_auto_20170804_1624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailycheckinlog',
            name='is_continue',
            field=models.BooleanField(default=False, verbose_name='连签奖励'),
        ),
    ]
