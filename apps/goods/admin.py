from django.contrib import admin
from goods.models import GoodsType, IndexGoodsBanner, IndexTypeGoodsBanner, IndexPromotionBanner
from django.core.cache import cache

from goods.models import Goods, GoodsSKU, GoodsImage


# Register your models here.
class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """新增或更新表中的数据时调用"""
        super().save_model(request, obj, form, change)

        # 发出任务，进行静态页面更新
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清楚首页的缓存数据
        cache.delete('index_page_data')

    def delete_mode(self, request, obj):
        """删除表中的数据时调用"""
        super().delete_mode(request, obj)
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清楚首页的缓存数据
        cache.delete('index_page_data')


class GoodsTypeAdmin(BaseModelAdmin):
    list_display = ['id', 'name']


class IndexGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['index', 'sku']


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['index', 'type']


class IndexPromotionBannerAdmin(BaseModelAdmin):
    list_display = ['index', 'name']


class GoodsAdmin(BaseModelAdmin):
    list_display = ['id', 'name']


class GoodsSKUAdmin(BaseModelAdmin):
    list_display = ['id', 'name', 'stock', 'sales']


admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)

admin.site.register(Goods, GoodsAdmin)
admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(GoodsImage)