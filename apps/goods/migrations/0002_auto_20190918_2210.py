# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('goods', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='goodssku',
            name='status',
            field=models.SmallIntegerField(verbose_name='商品状态', default=1, choices=[(1, '上线'), (0, '下线')]),
        ),
        migrations.AlterField(
            model_name='indexpromotionbanner',
            name='url',
            field=models.CharField(verbose_name='活动链接', max_length=256),
        ),
    ]
