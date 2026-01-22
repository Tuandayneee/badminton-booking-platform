from django.db import models
from users.models import CustomerProfile
from partner.models import Court
from django.conf import settings


class FixedSchedule(models.Model):
    """
    Quản lý khách đặt lịch cố định (VD: Thứ 3-5-7 hàng tuần trong 3 tháng)
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fixed_schedules', verbose_name="Khách hàng")
    court = models.ForeignKey(Court, on_delete=models.CASCADE, verbose_name="Sân")
    
    start_date = models.DateField(verbose_name="Ngày bắt đầu")
    end_date = models.DateField(verbose_name="Ngày kết thúc")
    
    # Lưu dạng JSON danh sách thứ: [1, 3, 5] tương ứng T3, T5, T7
    days_of_week = models.JSONField(verbose_name="Thứ trong tuần") 
    
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    
    total_months = models.IntegerField(default=1, verbose_name="Số tháng đăng ký")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lịch cố định: {self.user.username} - {self.court.name}"    
class Booking(models.Model):
    class Status(models.TextChoices):
        
        CONFIRMED = 'confirmed', 'Thanh toán'
        CHECKED_IN = 'checked_in', 'Đã nhận sân '
        COMPLETED = 'completed', 'Hoàn thành'
        ADMIN_CANCELLED = 'admin_cancelled', 'Hủy bởi Admin'

    booking_code = models.CharField(max_length=20, unique=True, verbose_name="Mã đặt chỗ")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings', verbose_name="Người dùng")
    fixed_schedule = models.ForeignKey(FixedSchedule, on_delete=models.SET_NULL, blank=True, null=True, related_name='bookings', verbose_name="Lịch cố định")
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings', verbose_name="Sân")
    date = models.DateField(verbose_name="Ngày đặt sân")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Tổng tiền")
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.CONFIRMED, 
        verbose_name="Trạng thái"
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    def __str__(self):
        return f"{self.booking_code} - {self.user.username}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['booking_code']),
        ]
class Transaction(models.Model):
      
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Tiền mặt'
        BANK_TRANSFER = 'bank_transfer', 'Chuyển khoản ngân hàng'

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='transaction', verbose_name="Đặt chỗ")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions', verbose_name="Người dùng")
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Số tiền")
    transaction_type = models.CharField(default='Thanh toán', max_length=50, verbose_name="Loại giao dịch")
    payment_method = models.CharField(choices=PaymentMethod.choices, max_length=50, verbose_name="Phương thức thanh toán")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Ngày giao dịch")
    def __str__(self):
        return f"{self.amount} - {self.payment_method}"
