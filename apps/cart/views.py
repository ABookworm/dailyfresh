from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection


# Create your views here.
class CartAddView(View):
    def post(self, request):
        """购物车记录添加"""
        # 接受数据
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理；添加购物车记录
        # 尝试获取
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 尝试获取sku_id的值
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 购物车已经有记录
            count += int(cart_count)
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})
        # 设置hash中sku_id 对应的值
        conn.hset(cart_key, sku_id, count)
        # 计算用户购物车中商品条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res': 5, 'message': '添加成功', 'total_count': total_count})


# /cart/
class CartInfoView(View):
    """购物车页面显示"""
    def get(self, request):
        # 获取登陆用户的购物车信息
        user = request.user
        if not user.is_authenticated():
            return redirect(reverse('user:login'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # {id : 数量}
        cart_dict = conn.hgetall(cart_key)

        skus = []
        total_count = 0
        total_price = 0
        # 遍历获取商品id, 数量
        for sku_id, count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品小计
            amount = sku.price * int(count)
            # 动态增加属性, 以便传参
            sku.amount = amount
            sku.count = count

            # 重新构建列表
            skus.append(sku)

            total_count += int(count)
            total_price += amount

        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
        }
        return render(request, 'cart.html', context)


# /cart/update
class CartUpdateView(View):
    def post(self, request):
        """购物车记录更新"""
        # 接受数据
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理；增加购物车记录
        # 尝试获取
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})

        # 设置hash中sku_id 对应的值
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 5, 'message': '更新成功', 'total_count': total_count})


# /cart/delete
class CartDeleteView(View):
    def post(self, request):
        """购物车记录删除"""
        # 接受数据
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')

        # 数据校验
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '无效商品ID'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理；增加购物车记录
        # 尝试获取
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 设置hash中sku_id 对应的值
        conn.hdel(cart_key, sku_id)

        # 计算用户购物车中商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        # 返回应答
        return JsonResponse({'res': 3, 'message': '删除成功', 'total_count': total_count})