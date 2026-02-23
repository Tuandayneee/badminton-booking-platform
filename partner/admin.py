from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Amenity, BadmintonCenter, CenterImage, Court, PriceRule,
    Product, ServiceOrder, ServiceOrderItem
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
    list_filter = ('is_active', 'partner__user__username')
    search_fields = ('name', 'address', 'partner__user__username')
    inlines = [CenterImageInline, PriceRuleInline] 
    filter_horizontal = ('amenities',)

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    # Đã bỏ court_type theo model của bạn
    list_display = ('name', 'center', 'base_price_per_hour','golden_price_per_hour','golden_start_time','golden_end_time', 'is_active')
    list_filter = ('center', 'is_active')
    search_fields = ('name', 'center__name')
    list_editable = ('is_active', 'base_price_per_hour')



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