from django.db import models
from users.models import CustomerProfile
from partner.models import Court, Customer  
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
        PENDING = 'pending', 'Chờ xác nhận'
        WAITING_VERIFY = 'waiting_verify', 'Chờ xác nhận thanh toán'    
        CONFIRMED = 'confirmed', 'Thanh toán'
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
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='bookings', verbose_name="Khách hàng")    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING, 
        verbose_name="Trạng thái"
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú")
    
    
    
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    def __str__(self):
        return f"{self.booking_code} - {self.user.username}"

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['court', 'date', 'start_time'], 
                name='unique_booking_slot',
                condition=~models.Q(status__in=['cancelled', 'admin_cancelled']) 
            )
        ]
class Transaction(models.Model):
      
    booking_group_code = models.CharField(max_length=100, verbose_name="Mã nhóm đơn hàng", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions', verbose_name="Người dùng")
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Số tiền")
    transaction_reference = models.CharField(max_length=100, unique=True, verbose_name="Mã bút toán (Bank Ref)")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Ngày giao dịch")
    is_verified = models.BooleanField(default=False, verbose_name="Đã xác nhận" )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Ngày xác nhận") 
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_transactions', verbose_name="Người xác nhận")
    def __str__(self):
        return f"{self.amount} - {self.transaction_reference}"
