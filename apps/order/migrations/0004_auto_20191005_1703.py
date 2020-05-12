# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0003_auto_20190918_2210'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordergoods',
            name='comment',
            field=models.CharField(verbose_name='评论', max_length=256, default=''),
        ),
        migrations.AlterField(
            model_name='orderinfo',
            name='order_status',
            field=models.SmallIntegerField(verbose_name='订单状态', default=1, choices=[(2, '待发货'), (4, '待评价'), (1, '待支付'), (3, '待收货'), (5, '已完成')]),
        ),
        migrations.AlterField(
            model_name='orderinfo',
            name='pay_method',
            field=models.SmallIntegerField(verbose_name='支付方式', default=3, choices=[(1, '货到付款'), (4, '银联支付'), (3, '支付宝'), (2, '微信支付')]),
        ),
        migrations.AlterField(
            model_name='orderinfo',
            name='trade_no',
            field=models.CharField(verbose_name='支付编号', max_length=128, default=''),
        ),
    ]
