from django.views.generic import View
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django_redis import get_redis_connection
from django.core.cache import cache

from order.models import OrderGoods
from django.core.paginator import Paginator


# Create your views here.
# http://127.0.0.1:8000/index
class IndexView(View):
    def get(self, request):
        """首页显示"""
        # 尝试从缓存中获取数据
        context = cache.get('index_page_data')

        if context is None:
            print("设置缓存")
            # 缓存中没有数据
            # 获取商品的种类信息
            types = GoodsType.objects.all()
            # 获取首页商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')

            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 获取首页分类商品分类信息
            for type in types:
                # 获取type种类首页分类商品图片展示信息
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
                # 获取type种类首页分类商品图片展示信息
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)
                # 动态给type增加属性，分别保存图片，文字展示信息
                type.image_banners = image_banners
                type.title_banners = title_banners

            # 组织模板上下文
            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners}

            # 设置缓存: key value timeout
            cache.set('index_page_data', context, 3600)

        # 获取购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已经登陆
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        # 此处不知何故用update方法就无法访给html传递参数
        # context = context.update(cart_count=cart_count)
        context['cart_count'] = cart_count

        return render(request, 'index.html', context)


# /goods/(goods_id)
class DetailView(View):
    """详情页面"""
    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取商品的评论信息
        sku_order = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同一个SPU其他规格
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已经登陆
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 溢出再次浏览项目
            conn.lrem(history_key, 0, goods_id)
            # 添加最新浏览
            conn.lpush(history_key, goods_id)
            # 仅保留前五项目
            conn.ltrim(history_key, 0, 4)

        context = {'sku': sku,
                   'types': types,
                   'sku_order': sku_order,
                   'new_skus': new_skus,
                   'same_spu_skus': same_spu_skus,
                   'cart_count': cart_count}

        return render(request, 'detail.html', context)


# /list/type_id/page?sort=排序方式
class ListView(View):
    """列表页面显示"""
    def get(self, request, type_id, page):
        # 获取种类信息
        try:
            type = GoodsType.objects.filter(id=type_id)
            for typ in type:
                typ_name = typ.name
        except GoodsType.DoesNotExist:
            # 种类不存在,跳转主页
            return redirect(reverse('goods:list'))

        # 获取商品种类信息
        types = GoodsType.objects.all()

        # 获取分类商品信息
        sort = request.GET.get('sort')
        if sort == "price":
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == "hot":
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')
            sort = 'default'

        # 对数据进行分类
        paginator = Paginator(skus, 1)

        # 获取第page的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的实例对象
        skus_page = paginator.page(page)

        # 进行页码控制
        # 1, 总页码小于5页，页面显示所有页码
        # 2, 页码为前三页， 显示1-5
        # 3， 页码为后三页，显示后五页
        # 其他情况，显示当前页的前2页，当前页，后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page < 2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取商品新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已经登陆
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        context = {
            'type_name': typ_name,
            'type_id': type_id,
            'sort': sort,
            'types': types,
            'skus_page': skus_page,
            'pages': pages,
            'new_skus': new_skus,
            'cart_count': cart_count,
        }

        # print(context)
        return render(request, 'list.html', context)
