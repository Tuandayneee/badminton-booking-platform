from django.shortcuts import render, redirect, get_object_or_404
from users.decorators import role_required
from partner.models import BadmintonCenter, Product
import json
from partner.models import ServiceOrder, ServiceOrderItem
from django.contrib import messages
from users.models import StaffProfile
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta


@role_required('staff', 'partner')
def pos_sales(request):
    """Trang POS bán hàng tại sân"""
    try:
        staff_profile = request.user.staff_profile
        center = staff_profile.center
    except StaffProfile.DoesNotExist:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')
    
    if not center:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')
    
    products = Product.objects.filter(center=center, is_active=True)
    
    if request.method == 'POST':
        cart_data_str = request.POST.get('cart_data')
        staff_name = request.POST.get('staff_name', request.user.full_name or request.user.username)
        payment_method = request.POST.get('payment_method', 'cash')
        
        try:
            cart_items = json.loads(cart_data_str)
            if not cart_items:
                messages.error(request, "Giỏ hàng trống!")
                return redirect('pos_sales')
            
            total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
            
            order = ServiceOrder.objects.create(
                center=center,
                staff_name=staff_name,
                total_amount=total_amount,
                payment_method=payment_method
            )
            
            for item in cart_items:
                product = Product.objects.filter(id=item['product_id']).first()
                ServiceOrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price_at_time=item['price']
                )
                
                if product and product.stock_quantity >= item['quantity']:
                    product.stock_quantity -= item['quantity']
                    product.save()
            
            messages.success(request, f"Đã tạo đơn hàng #{order.id} - Tổng: {int(total_amount):,}đ")
            return redirect('pos_sales')
            
        except (json.JSONDecodeError, KeyError) as e:
            messages.error(request, f"Lỗi dữ liệu: {e}")
            return redirect('pos_sales')
    
    context = {
        'center': center,
        'products': products,
    }
    return render(request, 'staff/pos.html', context)


@role_required('staff', 'partner')
def staff_sales_report(request):
    """Trang doanh thu bán hàng theo ngày cho nhân viên"""
    try:
        staff_profile = request.user.staff_profile
        center = staff_profile.center
    except StaffProfile.DoesNotExist:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')
    
    if not center:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')
    
    today = timezone.now().date()
    
    # Lọc theo ngày
    selected_date_str = request.GET.get('date')
    try:
        selected_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else today
    except ValueError:
        selected_date = today
    
    orders_today = ServiceOrder.objects.filter(
        center=center,
        created_at__date=selected_date
    ).order_by('-created_at')
    
    
    stats_today = orders_today.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id')
    )
    
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        day_revenue = ServiceOrder.objects.filter(
            center=center,
            created_at__date=day
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        chart_data.append(float(day_revenue))
    
    
    orders_with_items = []
    for order in orders_today:
        items = order.items.select_related('product').all()
        orders_with_items.append({
            'order': order,
            'items': items,
        })
    
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
    """Danh sách hóa đơn dịch vụ cho nhân viên"""
    try:
        staff_profile = request.user.staff_profile
        center = staff_profile.center
    except StaffProfile.DoesNotExist:
        messages.error(request, "bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')

    if not center:
        messages.error(request, "Bạn chưa được phân công vào trung tâm nào.")
        return redirect('home')

    today = timezone.now().date()
    selected_date_str = request.GET.get('date')
    try:
        selected_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else today
    except ValueError:
        selected_date = today

    orders = ServiceOrder.objects.filter(
        center=center,
        created_at__date=selected_date
    ).order_by('-created_at')

    stats = orders.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )

    orders_with_items = []
    for order in orders.prefetch_related('items__product'):
        items = order.items.all()
        orders_with_items.append({
            'order': order,
            'items': items,
        })

    context = {
        'center': center,
        'selected_date': selected_date,
        'today': today,
        'total_revenue': stats['total_revenue'] or 0,
        'total_orders': stats['total_orders'] or 0,
        'orders_with_items': orders_with_items,
    }
    return render(request, 'staff/service_orders.html', context)