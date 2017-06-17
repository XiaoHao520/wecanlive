# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-17 07:07
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_base', '0002_adminlog'),
        ('core', '0004_auto_20170616_1526'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtraPrize',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255, verbose_name='名称')),
                ('is_del', models.BooleanField(default=False, verbose_name='已删除')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否有效')),
                ('is_sticky', models.BooleanField(default=False, verbose_name='是否置顶')),
                ('sorting', models.SmallIntegerField(default=0, help_text='数字越大越靠前', verbose_name='排序')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
                ('required_amount', models.IntegerField(verbose_name='需要的单日金币消费额')),
            ],
            options={
                'db_table': 'core_extra_prize',
                'verbose_name': '附赠礼物',
                'verbose_name_plural': '附赠礼物',
            },
        ),
        migrations.CreateModel(
            name='PrizeCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255, verbose_name='名称')),
                ('is_del', models.BooleanField(default=False, verbose_name='已删除')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否有效')),
                ('is_sticky', models.BooleanField(default=False, verbose_name='是否置顶')),
                ('sorting', models.SmallIntegerField(default=0, help_text='数字越大越靠前', verbose_name='排序')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'core_prize_category',
                'verbose_name': '礼物分类',
                'verbose_name_plural': '礼物分类',
            },
        ),
        migrations.CreateModel(
            name='PrizeOrder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prizeorders_owned', to=settings.AUTH_USER_MODEL, verbose_name='作者')),
                ('live_watch_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prize_orders', to='core.LiveWatchLog', verbose_name='观看记录')),
            ],
            options={
                'db_table': 'core_prize',
                'verbose_name': '礼物订单',
                'verbose_name_plural': '礼物订单',
            },
        ),
        migrations.AddField(
            model_name='prize',
            name='date_sticker_begin',
            field=models.DateTimeField(blank=True, null=True, verbose_name='表情包有效期开始'),
        ),
        migrations.AddField(
            model_name='prize',
            name='date_sticker_end',
            field=models.DateTimeField(blank=True, null=True, verbose_name='表情包有效期结束'),
        ),
        migrations.AddField(
            model_name='prize',
            name='icon',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prize_as_icon', to='django_base.ImageModel', verbose_name='图标'),
        ),
        migrations.AddField(
            model_name='prize',
            name='marquee_size',
            field=models.CharField(choices=[('BIG', '大'), ('SMALL', '小')], default='SMALL', max_length=20, verbose_name='跑马灯大小'),
        ),
        migrations.AddField(
            model_name='prize',
            name='price',
            field=models.IntegerField(default=0, verbose_name='价格（金币）'),
        ),
        migrations.AddField(
            model_name='prize',
            name='stickers',
            field=models.ManyToManyField(blank=True, related_name='prizes_as_stickers', to='django_base.ImageModel', verbose_name='表情包'),
        ),
        migrations.AddField(
            model_name='prizeorder',
            name='prize',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='core.Prize', verbose_name='礼物'),
        ),
        migrations.AddField(
            model_name='prizeorder',
            name='prize_transition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='core.PrizeTransition', verbose_name='礼物记录'),
        ),
        migrations.AddField(
            model_name='extraprize',
            name='prize',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_prizes', to='core.Prize', verbose_name='礼物'),
        ),
        migrations.AddField(
            model_name='extraprize',
            name='wallpaper',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='extra_prize_as_wallpaper', to='django_base.ImageModel', verbose_name='壁纸'),
        ),
        migrations.AddField(
            model_name='prize',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prizes', to='core.PrizeCategory', verbose_name='礼物分类'),
        ),
    ]
