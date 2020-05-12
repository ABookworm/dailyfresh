# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0002_auto_20190904_2119'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderinfo',
            name='order_status',
            field=models.SmallIntegerField(verbose_name='订单状态', default=1, choices=[(5, '已完成'), (1, '待支付'), (2, '待发货'), (3, '待收货'), (4, '待评价')]),
        ),
        migrations.AlterField(
            model_name='orderinfo',
            name='pay_method',
            field=models.SmallIntegerField(verbose_name='支付方式', default=3, choices=[(1, '货到付款'), (4, '银联支付'), (2, '微信支付'), (3, '支付宝')]),
        ),
    ]
