# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-15 12:52
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_merge_20170915_1237'),
    ]

    operations = [
        migrations.AddField(
            model_name='livewatchlog',
            name='coin_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.CreditCoinTransaction', verbose_name='收费直播缴费记录'),
        ),
    ]
