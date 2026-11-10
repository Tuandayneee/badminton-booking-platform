from datetime import timedelta
import json

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from partner.models import Product, ServiceOrder, ServiceOrderItem
from users.decorators import role_required
from users.models import StaffProfile


def _get_staff_center(request):
    try:
        center = request.user.staff_profile.center
    except StaffProfile.DoesNotExist:
        center = None
    if not center:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
    return center


@role_required('staff', 'partner')
def pos_sales(request):
    """Trang POS bán hàng tại sân."""
    center = _get_staff_center(request)
    if not center:
        return redirect('home')

    products = Product.objects.filter(center=center, is_active=True)

    if request.method == 'POST':
        cart_data_str = request.POST.get('cart_data', '')
        staff_name = (
            request.POST.get('staff_name', '').strip()
            or request.user.full_name
            or request.user.username
        )
        payment_method = request.POST.get('payment_method', ServiceOrder.PaymentMethod.CASH)
        valid_methods = dict(ServiceOrder.PaymentMethod.choices)
        if payment_method not in valid_methods:
            payment_method = ServiceOrder.PaymentMethod.CASH

        try:
            cart_items = json.loads(cart_data_str)
            if not isinstance(cart_items, list) or not cart_items:
                messages.error(request, "Giỏ hàng trống!")
                return redirect('pos_sales')

            with transaction.atomic():
                total_amount = 0
                order_items_to_create = []

                for item in cart_items:
                    if not isinstance(item, dict):
                        raise ValueError("Dữ liệu sản phẩm không hợp lệ")
                    product_id = item.get('product_id')
                    quantity = int(item.get('quantity', 0))
                    if quantity <= 0:
                        raise ValueError("Số lượng sản phẩm phải lớn hơn 0")

                    product = Product.objects.select_for_update().filter(
                        id=product_id,
                        center=center,
                        is_active=True,
                    ).first()
                    if not product:
                        raise ValueError("Sản phẩm không tồn tại hoặc không thuộc trung tâm này")

                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Sản phẩm '{product.name}' chỉ còn {product.stock_quantity} trong kho"
                        )

                    product.stock_quantity -= quantity
                    product.save(update_fields=['stock_quantity'])

                    line_price = product.price
                    total_amount += line_price * quantity
                    order_items_to_create.append((product, quantity, line_price))

                order = ServiceOrder.objects.create(
                    center=center,
                    staff_name=staff_name,
                    total_amount=total_amount,
                    payment_method=payment_method,
                )

                ServiceOrderItem.objects.bulk_create([
                    ServiceOrderItem(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price_at_time=line_price,
                    )
                    for product, quantity, line_price in order_items_to_create
                ])

            messages.success(request, f"Đã tạo đơn hàng #{order.id} - Tổng: {int(total_amount):,}đ")
            return redirect('pos_sales')

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            messages.error(request, f"Không thể tạo đơn hàng: {exc}")
            return redirect('pos_sales')

    context = {
        'center': center,
        'products': products,
    }
    return render(request, 'staff/pos.html', context)


@role_required('staff', 'partner')
def staff_sales_report(request):
    """Trang doanh thu bán hàng theo ngày cho nhân viên."""
    center = _get_staff_center(request)
    if not center:
        return redirect('home')

    today = timezone.localdate()
    selected_date_str = request.GET.get('date')
    try:
        selected_date = (
            timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if selected_date_str
            else today
        )
    except ValueError:
        selected_date = today

    orders_today = (
        ServiceOrder.objects.filter(center=center, created_at__date=selected_date)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    stats_today = orders_today.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )

    seven_days_ago = today - timedelta(days=6)
    daily_totals = (
        ServiceOrder.objects.filter(
            center=center,
            created_at__date__gte=seven_days_ago,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('total_amount'))
    )
    revenue_by_day = {entry['day']: float(entry['total'] or 0) for entry in daily_totals}

    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(revenue_by_day.get(day, 0.0))

    orders_with_items = [
        {'order': order, 'items': order.items.all()}
        for order in orders_today
    ]

    context = {
        'center': center,
        'selected_date': selected_date,
        'today': today,
        'total_revenue': stats_today['total_revenue'] or 0,
        'total_orders': stats_today['total_orders'] or 0,
        'orders_with_items': orders_with_items,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'staff/sales_report.html', context)


@role_required('staff', 'partner')
def staff_service_orders(request):
    """Danh sách hóa đơn dịch vụ cho nhân viên."""
    center = _get_staff_center(request)
    if not center:
        return redirect('home')

    today = timezone.localdate()
    selected_date_str = request.GET.get('date')
    try:
        selected_date = (
            timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if selected_date_str
            else today
        )
    except ValueError:
        selected_date = today

    orders = (
        ServiceOrder.objects.filter(center=center, created_at__date=selected_date)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    stats = orders.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )

    orders_with_items = [
        {'order': order, 'items': order.items.all()}
        for order in orders
    ]

    context = {
        'center': center,
        'selected_date': selected_date,
        'today': today,
        'total_revenue': stats['total_revenue'] or 0,
        'total_orders': stats['total_orders'] or 0,
        'orders_with_items': orders_with_items,
    }
    return render(request, 'staff/service_orders.html', context)
