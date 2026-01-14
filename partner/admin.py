from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Amenity, BadmintonCenter, CenterImage, Court, PriceRule,
    Booking, FixedSchedule, Product, ServiceOrder, ServiceOrderItem
)

# ==============================================================================
# INLINES (Nhập liệu phụ trong trang chính)
# ==============================================================================

class CenterImageInline(admin.TabularInline):
    """Cho phép up nhiều ảnh ngay trong trang sửa Cụm sân"""
    model = CenterImage
    extra = 1 

class ServiceOrderItemInline(admin.TabularInline):
    """Cho phép nhập món ăn/đồ uống ngay trong trang đơn hàng"""
    model = ServiceOrderItem
    extra = 0
    readonly_fields = ('price_at_time',)

class PriceRuleInline(admin.TabularInline):
    """Cấu hình giá động ngay trong trang Cụm sân"""
    model = PriceRule
    extra = 0

# ==============================================================================
# MODEL ADMINS
# ==============================================================================

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_icon')
    
    def display_icon(self, obj):
        if obj.icon:
            return format_html('<img src="{}" width="30" height="30" />', obj.icon.url)
        return "-"
    display_icon.short_description = 'Icon'

@admin.register(BadmintonCenter)
class BadmintonCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner', 'open_time', 'close_time', 'is_active', 'created_at')
    list_filter = ('is_active', 'partner__business_name')
    search_fields = ('name', 'address', 'partner__user__username')
    inlines = [CenterImageInline, PriceRuleInline] 
    filter_horizontal = ('amenities',)

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    # Đã bỏ court_type theo model của bạn
    list_display = ('name', 'center', 'base_price_per_hour', 'is_active')
    list_filter = ('center', 'is_active')
    search_fields = ('name', 'center__name')
    list_editable = ('is_active', 'base_price_per_hour')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    # Lưu ý: Model của bạn dùng 'date', không phải 'booking_date'
    list_display = ('booking_code', 'user_info', 'court_info', 'date', 'time_range', 'total_price', 'status_colored', 'is_paid')
    list_filter = ('status', 'is_paid', 'date', 'court__center')
    search_fields = ('booking_code', 'user__username', 'court__name')
    readonly_fields = ('booking_code', 'created_at')
    date_hierarchy = 'date' 

    def user_info(self, obj):
        # Model bạn hiện tại chỉ có User, không có guest_name/guest_phone nên tôi chỉ hiển thị User
        return f"{obj.user.username}"
    user_info.short_description = 'Khách hàng'

    def court_info(self, obj):
        return f"{obj.court.name} - {obj.court.center.name}"
    court_info.short_description = 'Sân'

    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_range.short_description = 'Khung giờ'

    def status_colored(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'checked_in': 'green',
            'completed': 'gray',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = 'Trạng thái'

@admin.register(FixedSchedule)
class FixedScheduleAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'customer_phone', 'center', 'days_display', 'date_range', 'is_active')
    list_filter = ('center', 'is_active')
    search_fields = ('customer_name', 'customer_phone')

    def days_display(self, obj):
        day_map = {0:'T2', 1:'T3', 2:'T4', 3:'T5', 4:'T6', 5:'T7', 6:'CN'}
        try:
            return ", ".join([day_map.get(d, str(d)) for d in obj.days_of_week])
        except:
            return str(obj.days_of_week)
    days_display.short_description = 'Thứ'

    def date_range(self, obj):
        return f"{obj.start_date.strftime('%d/%m')} - {obj.end_date.strftime('%d/%m')}"
    date_range.short_description = 'Thời hạn'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'price', 'stock_quantity', 'is_active')
    list_filter = ('center', 'is_active')
    search_fields = ('name',)
    list_editable = ('stock_quantity', 'price')

@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    # Model ServiceOrder của bạn KHÔNG có trường booking, nên tôi đã bỏ nó ra khỏi list_display
    list_display = ('id', 'center', 'staff_name', 'total_amount', 'created_at')
    list_filter = ('center', 'created_at')
    inlines = [ServiceOrderItemInline]