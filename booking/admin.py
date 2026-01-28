from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import intcomma
from .models import FixedSchedule, Booking, Transaction
from .services import process_approve_transaction
@admin.register(FixedSchedule)
class FixedScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'user_info', 
        'court', 
        'date_range', 
        'time_range', 
        'days_display', 
        'is_active',
        'created_at'
    )
    list_filter = ('is_active', 'court', 'start_date')
    search_fields = ('user__username', 'user__email', 'court__name')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Thông tin khách hàng & Sân', {
            'fields': ('user', 'court', 'is_active')
        }),
        ('Thời gian cố định', {
            'fields': ('start_date', 'end_date', 'total_months', 'days_of_week')
        }),
        ('Khung giờ', {
            'fields': ('start_time', 'end_time')
        }),
    )

    def user_info(self, obj):
        return obj.user.username
    user_info.short_description = "Khách hàng"

    def date_range(self, obj):
        return f"{obj.start_date.strftime('%d/%m')} - {obj.end_date.strftime('%d/%m/%Y')}"
    date_range.short_description = "Thời gian áp dụng"

    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_range.short_description = "Khung giờ"

    def days_display(self, obj):
        # Mapping số sang thứ (Giả sử 0=Thứ 2, 6=Chủ nhật theo chuẩn Python)
        # Nếu hệ thống của bạn quy định khác (VD: 1=CN) thì sửa lại map này nhé
        day_map = {
            0: 'T2', 1: 'T3', 2: 'T4', 3: 'T5', 
            4: 'T6', 5: 'T7', 6: 'CN'
        }
        if not obj.days_of_week:
            return "---"
        
        # Sắp xếp và convert
        try:
            days = sorted([int(d) for d in obj.days_of_week])
            labels = [day_map.get(d, str(d)) for d in days]
            return ", ".join(labels)
        except:
            return str(obj.days_of_week)
            
    days_display.short_description = "Các thứ"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_code', 
        'customer_info',
        'court', 
        'date', 
        'time_range', 
        'total_price_formatted', 
        'status_badge', 
        'is_fixed_schedule'
    )
    list_filter = ('status', 'date', 'court', 'created_at')
    search_fields = ('booking_code', 'customer__name', 'customer__phone', 'court__name')
    readonly_fields = ('booking_code', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'date'

    fieldsets = (
        ('Thông tin chung', {
            'fields': ('booking_code', 'status', 'created_at')
        }),
        ('Khách hàng', {
            'fields': ('customer', 'user')
        }),
        ('Chi tiết đặt sân', {
            'fields': ('court', 'fixed_schedule', 'date')
        }),
        ('Thời gian & Chi phí', {
            'fields': (('start_time', 'end_time'), 'total_price')
        }),
        ('Ghi chú', {
            'fields': ('note',)
        }),
    )

    def customer_info(self, obj):
        if obj.customer:
            return f"{obj.customer.name} - {obj.customer.phone}"
        return "---"
    customer_info.short_description = "Khách hàng"

    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_range.short_description = "Giờ chơi"

    def total_price_formatted(self, obj):
        # Cần cài đặt 'django.contrib.humanize' trong INSTALLED_APPS để dùng intcomma
        # Hoặc dùng f"{obj.total_price:,.0f} đ".replace(",", ".")
        return f"{obj.total_price:,.0f} VND"
    total_price_formatted.short_description = "Tổng tiền"

    def is_fixed_schedule(self, obj):
        return bool(obj.fixed_schedule)
    is_fixed_schedule.boolean = True
    is_fixed_schedule.short_description = "Lịch cố định?"

    def status_badge(self, obj):
        """Tạo màu sắc cho trạng thái để dễ nhìn"""
        colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'checked_in': 'blue',
            'completed': 'gray',
            'admin_cancelled': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 10px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Trạng thái"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('booking_group_code', 'user', 'amount', 'transaction_reference', 'is_verified', 'timestamp')
    list_filter = ('is_verified', 'timestamp')
    search_fields = ('booking_group_code', 'transaction_reference', 'user__phone_number')
    
    actions = ['approve_transactions_action']
    def save_model(self, request, obj, form, change):
        if 'is_verified' in form.changed_data and obj.is_verified:
            process_approve_transaction(obj, request.user)
        
        # Gọi hàm save gốc để lưu vào DB
        super().save_model(request, obj, form, change)
    @admin.action(description='Duyệt thanh toán (Xác nhận tiền đã về)')
    def approve_transactions_action(self, request, queryset):
        count = 0
        for trans in queryset:
            if process_approve_transaction(trans, request.user):
                count += 1
                
        self.message_user(request, f"Đã duyệt thành công {count} giao dịch.")