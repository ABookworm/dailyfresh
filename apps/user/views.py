from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.views.generic import View
from user.models import User, Address
from order.models import OrderInfo, OrderGoods
from django.core.paginator import Paginator
import re

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from django.http import HttpResponse

from celery_tasks.tasks import send_register_active_mail

from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin

from django_redis import get_redis_connection
from goods.models import GoodsSKU
# Create your views here.
# /user/register


def register(request):
    """注册"""
    if request.method == "GET":
        return render(request, 'register.html')
    else:
        """注册表单的处理"""
        # 1. 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        check_box = request.POST.get('allow')

        # 2. 验证数据
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 验证邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 验证协议
        if check_box != 'on':
            return render(request, 'register.html', {'errmsg': '请同意用户协议'})

        # 验证是否用户名重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在，可用
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已被使用'})
        # 3. 处理业务数据: 进行注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 4. 返回结果
        return redirect(reverse('goods:index'))


class RegisterView(View):
    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """处理注册表单数据"""
        # 1. 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        check_box = request.POST.get('allow')

        # 2. 验证数据
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 验证邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 验证协议
        if check_box != 'on':
            return render(request, 'register.html', {'errmsg': '请同意用户协议'})
        # 验证是否用户名重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在，可用
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已被使用'})
        # 3. 处理业务数据: 进行注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 邮箱激活, 并加密信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        # 发送邮件
        send_register_active_mail.delay(email, username, token)

        # 4. 返回结果
        return redirect(reverse('goods:index'))


class ActiveView(View):
    def get(self, request, token):
        """激活视图"""
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            # 解密成功
            info = serializer.loads(token)
            user_id = info['confirm']
            # 获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 激活成功，跳转登陆页
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            # 激活链接已经过期
            return HttpResponse('激活链接已过期！')


class LoginView(View):
    def get(self, request):
        """登陆页面"""
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登陆数据处理"""
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 处理
        user = authenticate(username=username, password=password)
        if user is not None:
            """用户存在"""
            if user.is_active:
                # 用户激活，记录登陆状态
                login(request, user)

                # 增加登陆后是否仍要动作：获取登陆后所要跳转的地址(默认index)
                next_url = request.GET.get('next', reverse('goods:index'))

                # 跳转到next_url
                response = redirect(next_url)  # HttpResponseRedirect 子类

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                return response
            else:
                # 用户没有激活
                return render(request, 'login.html', {'errmsg':'该用户未激活'})
        else:
            # 用户不存在
            return render(request, 'login.html', {'errmsg': '用户不存在'})


# /logout
class LogoutView(View):
    """退出登陆"""
    def get(self, request):
        # django清除用户session信息
        logout(request)
        return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    """用户中心-信息页"""
    def get(self, request):
        """显示"""
        # page = user
        # django框架会自动传递request.user给模板文件
        user = request.user
        address = Address.objects.get_default_address(user)

        con = get_redis_connection('default')

        history_key = 'history_%d' % user.id
        # 获取用户历史浏览记录
        sku_ids = con.lrange(history_key, 0, 4)

        goods_list = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_list.append(goods)

        context = {'page': 'user',
                   'address':address,
                   'goods_list': goods_list}

        return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户中心-订单页"""
    def get(self, request, page):
        """显示订单页面"""
        # todo: 获取用户订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取商品信息
        for order in orders:
            # 根据订单获取商品信息
            order_skus = OrderGoods.objects.filter(order=order)

            # todo: 计算小计
            for order_sku in order_skus:
                # 获取商品数量
                amount = order_sku.price * order_sku.count
                # 动态增加属性
                order_sku.amount = amount

            # todo: 保存订单商品信息
            # 动态增加属性
            order.order_skus = order_skus
            order.status_name = order.ORDER_STATUS[order.order_status]

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的实例对象
        order_page = paginator.page(page)

        # todo: 进行页码控制
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

        # 组织上下文
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order'
        }

        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    """用户中心-地址页"""
    def get(self, request):
        """网页显示"""
        # 处理数据
        user = request.user
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        """表单提交"""
        # 无默认，设默认，有默认，不显示
        # 接受数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机格式不正确'})

        # 处理数据
        user = request.user
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答
        return redirect(reverse('user:address'))