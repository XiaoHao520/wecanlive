# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-08-28 12:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_remove_movie_live'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='live',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='movies', to='core.Live', verbose_name='直播'),
        ),
    ]