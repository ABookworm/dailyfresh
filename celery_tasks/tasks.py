# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import time

import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()

from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django.template import loader, RequestContext


# 创建实例对象
app = Celery('celery_tasks.tasks', broker='redis://192.168.3.9:6379/8')


# 定义任务函数
@app.task
def send_register_active_mail(to_email, username, token):
    """发送激活邮件"""
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_msg = "<h1>%s, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户：<br/><a href='http://127.0.0.1:8000/user/active/%s'>http" \
               "://127.0.0.1:8000/user/active/%s</a>" % (username, token, token)

    send_mail(subject, message, sender, receiver, html_message=html_msg)
    time.sleep(5)


@app.task
def generate_static_index_html():
    """产生首页静态页面"""
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

    # 使用模板
    # 1.加载模板文件
    temp = loader.get_template('static_base.html')
    # 定义模板上下文(可省略)
    # context = RequestContext(request, context)
    # 3.模板渲染——》完成页面内容
    static_index_html = temp.render(context)
    # 生成首页对应的静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w') as f:
        f.write(static_index_html)