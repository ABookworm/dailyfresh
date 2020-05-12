from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from user.models import Address
from order.models import OrderInfo, OrderGoods

from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from datetime import datetime
from django.db import transaction
from alipay import AliPay
from django.core.management import settings
import os
from django.core.paginator import Paginator

# Create your views here.
# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    """提交订单页面"""

    def post(self, request):
        """提交订单页面显示"""
        user = request.user
        # 获取sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        # 校验数据
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 遍历，获取用户需要购买的商品信息
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取
            count = conn.hget(cart_key, sku_id)
            # 计算商品小计
            amount = sku.price*int(count)
            # 动态给SKU增加属性
            sku.count = count
            sku.amount = amount
            # 添加
            skus.append(sku)
            # 累加
            total_count += int(count)
            total_price += amount

        # 运费：实际开发为子系统
        transit_price = 10
        # 实际付款
        total_pay = total_price + transit_price

        # 获取用户收件地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)

        context = {
            'skus': skus,

            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids': sku_ids
        }
        # print(skus)
        return render(request, 'place_order.html', context)


# 悲观锁
class OrderCommitView1(View):
    """订单提交"""
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登陆
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')  # 1, 3

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法支付方式'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '非法地址'})

        # todo: 核心业务处理
        # 组织参数
        # 创建订单ID
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10

        total_count = 0
        total_price = 0

        # 设置保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info 表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo: 用户的订单里面有几个商品，就向df_order_goods添加几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # select * from df_goods_sku where id=sku for update;
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    # 商品不存在
                    transaction.rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                print('user: %d stock: %d' % (user.id, sku.stock))
                import time
                time.sleep(10)

                # 获取购买数量
                count = conn.hget(cart_key, sku_id)
                # todo: 判断商品库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '库存不足'})

                # todo: 向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

                # 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo: 计算订单商品的总数量和总价格
                amount = sku.price * int(count)
                total_count += int(count)
                total_price += amount

            # todo: 更新总数目和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo: 删除购物车中的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 5, 'message': '订单创建成功'})


# 乐观锁
class OrderCommitView(View):
    """订单提交"""
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登陆
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')  # 1, 3

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法支付方式'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '非法地址'})

        # todo: 核心业务处理
        # 组织参数
        # 创建订单ID
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10

        total_count = 0
        total_price = 0

        # 设置保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info 表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo: 用户的订单里面有几个商品，就向df_order_goods添加几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品的信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        # 商品不存在
                        transaction.rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                    # 获取购买数量
                    count = conn.hget(cart_key, sku_id)
                    # todo: 判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '库存不足'})

                    # todo: 更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # 调试语句
                    # print('user: %d, times: %d, stock: %d' % (user.id, i, sku.stock))
                    # import time
                    # time.sleep(10)

                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock = orgin_stock
                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试的第三次，下单失败
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo: 计算订单商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                    # 更新成功，跳出循环
                    break

            # todo: 更新总数目和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo: 删除购物车中的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 5, 'message': '订单创建成功'})


class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        """订单支付"""
        # 用户是否登陆
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单ID'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理： 使用python sdk调用支付宝的支付接口
        alipay = AliPay(
            appid="2016101200668392",
            app_notify_url=None,
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",
            debug=True
        )
        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),
            subject='天天生鲜%s' % order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


# ajax post /order/check
class CheckPayView(View):
    """查询支付结果"""
    def post(self, request):
        """获取交易结果"""
        # 用户是否登陆
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})

        # 接受参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单ID'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理： 使用python sdk调用支付宝的支付接口
        alipay = AliPay(
            appid="2016101200668392",
            app_notify_url=None,
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",
            debug=True
        )

        # 调用支付宝的查询结果
        while True:
            response = alipay.api_alipay_trade_query(order_id)

            # response = {
            #     "trade_no": "2017032121001004070200176844",  # 支付宝交易号
            #     "code": "10000",  # 接口调用是否成功
            #     "invoice_amount": "20.00",
            #     "open_id": "20880072506750308812798160715407",
            #     "fund_bill_list": [
            #         {
            #             "amount": "20.00",
            #             "fund_channel": "ALIPAYACCOUNT"
            #         }
            #     ],
            #     "buyer_logon_id": "csq***@sandbox.com",
            #     "send_pay_date": "2017-03-21 13:29:17",
            #     "receipt_amount": "20.00",
            #     "out_trade_no": "out_trade_no15",
            #     "buyer_pay_amount": "20.00",
            #     "buyer_user_id": "2088102169481075",
            #     "msg": "Success",
            #     "point_amount": "0.00",
            #     "trade_status": "TRADE_SUCCESS",  # 支付结果
            #     "total_amount": "20.00"
            # }

            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # - 获取支付宝交易号
                trade_no = response.get('trade_no')
                # - 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                # - 返回结果
                return JsonResponse({'res': 0, 'message': '支付成功'})

            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款 or 业务处理失败，可能等待一会儿就可以成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res': 1, 'errmsg': '支付失败'})


class CommentView(View):
    """评价页面"""
    def get(self, request, order_id):
        """显示订单评价页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取订单商品
        order_skus = OrderGoods.objects.filter(order_id=order_id)

        # 计算小计
        for order_sku in order_skus:
            # 获取商品数量
            amount = order_sku.price * order_sku.count
            # 动态增加属性
            order_sku.amount = amount

        # 保存订单商品信息
        # 动态增加属性
        order.order_skus = order_skus
        order.status_name = order.ORDER_STATUS[order.order_status]

        print(order)

        return render(request, 'user_comment.html', {'order': order})

    def post(self, request, order_id):
        """提交处理订单评价页面"""
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)

        # 循环获取订单商品的内容
        for i in range(1, total_count+1):
            # 获取评论商品的ID
            sku_id = request.POST.get("sku_%d" % i)
            # 获取评论商品内容
            content = request.POST.get("content_%d" % i, '')

            print(sku_id)
            print(content)

            # 查询order_goods对应的内容，并写入
            try:
                order_goods = OrderGoods.objects.get(order=order, sku=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            print(order_goods)
            order_goods.comment = content
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))