from django.contrib import admin
from django.utils.html import format_html

from .models import Booking, Transaction
from .services import process_approve_transaction


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
    )
    list_filter = ('status', 'date', 'court', 'created_at')
    search_fields = ('booking_code', 'group_code', 'customer__name', 'customer__phone', 'court__name')
    readonly_fields = ('booking_code', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'date'

    fieldsets = (
        ('Thông tin chung', {
            'fields': ('booking_code', 'group_code', 'status', 'created_at'),
        }),
        ('Khách hàng', {
            'fields': ('customer', 'user'),
        }),
        ('Chi tiết đặt sân', {
            'fields': ('court', 'date'),
        }),
        ('Thời gian & Chi phí', {
            'fields': (('start_time', 'end_time'), 'total_price'),
        }),
        ('Ghi chú', {
            'fields': ('note',),
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
        return f"{obj.total_price:,.0f} VND"
    total_price_formatted.short_description = "Tổng tiền"

    def status_badge(self, obj):
        """Tạo màu sắc cho trạng thái để dễ nhìn."""
        colors = {
            Booking.Status.PENDING: 'orange',
            Booking.Status.WAITING_VERIFY: '#eab308',
            Booking.Status.CONFIRMED: 'green',
            Booking.Status.COMPLETED: 'gray',
            Booking.Status.ADMIN_CANCELLED: 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 10px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
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
            if not change:
                obj.is_verified = False
                super().save_model(request, obj, form, change)
            else:
                Transaction.objects.filter(pk=obj.pk).update(
                    booking_group_code=obj.booking_group_code,
                    user=obj.user,
                    amount=obj.amount,
                    transaction_reference=obj.transaction_reference,
                )
            process_approve_transaction(obj, request.user)
            obj.refresh_from_db()
            return
        super().save_model(request, obj, form, change)

    @admin.action(description='Duyệt thanh toán (Xác nhận tiền đã về)')
    def approve_transactions_action(self, request, queryset):
        count = 0
        for trans in queryset:
            if process_approve_transaction(trans, request.user):
                count += 1

        self.message_user(request, f"Đã duyệt thành công {count} giao dịch.")
