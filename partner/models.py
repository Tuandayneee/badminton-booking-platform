from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User, PartnerProfile 
from django.utils.translation import gettext_lazy as _


class Amenity(models.Model):
    name = models.CharField(max_length=50, verbose_name="Tên tiện ích")
    icon = models.ImageField(upload_to='amenities/', verbose_name="Icon")
    def __str__(self):
        return self.name
    
class BadmintonCenter(models.Model):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='centers', verbose_name="Đối tác")
    name = models.CharField(max_length=100, verbose_name="Tên trung tâm")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Vĩ độ")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Kinh độ")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    amenities = models.ManyToManyField(Amenity, blank=True,  verbose_name="Tiện ích")
    open_time = models.TimeField(default='07:00', verbose_name="Giờ mở cửa")
    close_time = models.TimeField(default='23:55', verbose_name="Giờ đóng cửa")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động") 
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
    
class CenterImage(models.Model):
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE, related_name='images', verbose_name="Trung tâm cầu lông")
    image = models.ImageField(upload_to='center_images/', verbose_name="Hình ảnh trung tâm")
    is_thumbnail = models.BooleanField(default=False, verbose_name="Ảnh đại diện")
    def __str__(self):
        return f"Image for {self.center.name}"
    

class Court(models.Model):
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE, related_name='courts')
    name = models.CharField(max_length=50, verbose_name="Tên sân") 
    base_price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá cơ bản/giờ")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    def __str__(self):
        return f"{self.center.name} - {self.name}"
class PriceRule(models.Model):
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE, related_name='price_rules')
    name = models.CharField(max_length=100, verbose_name="Tên khung giờ")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    days_of_week = models.JSONField(default=list, verbose_name="Ngày trong tuần áp dụng (0=Thứ 2, 6=Chủ nhật)")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá/giờ")
    priority = models.IntegerField(default=1, verbose_name="Độ ưu tiên")
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Chờ thanh toán'),
        ('confirmed', 'Đã đặt cọc/Thanh toán'),
        ('checked_in', 'Đã nhận sân '),
        ('completed', 'Hoàn thành'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Người dùng")
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings', verbose_name="Sân")
    date = models.DateField(verbose_name="Ngày đặt sân")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Tổng tiền")
    is_paid = models.BooleanField(default=False, verbose_name="Đã thanh toán")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, verbose_name="Ghi chú")
    booking_code = models.CharField(max_length=12, unique=True, verbose_name="Mã check-in")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['date', 'status']), # Tối ưu tìm kiếm lịch trống
            models.Index(fields=['booking_code']), # Tối ưu quét QR
        ]

class FixedSchedule(models.Model):
    """
    Lịch cố định 
    """
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE)
    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100, verbose_name="Tên chủ nhóm")
    customer_phone = models.CharField(max_length=20, verbose_name="SĐT chủ nhóm")
    start_time = models.TimeField()
    end_time = models.TimeField()
    days_of_week = models.JSONField(verbose_name="Các thứ trong tuần (VD: [1,3,5])")
    
    start_date = models.DateField(verbose_name="Ngày bắt đầu gói")
    end_date = models.DateField(verbose_name="Ngày kết thúc gói")
    
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)

class Product(models.Model):
    """
    Sản phẩm bán kèm: Nước ngọt, Cầu lông, Thuê vợt, Thuê giày...
    """
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, verbose_name="Tên sản phẩm")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Đơn giá")
    stock_quantity = models.IntegerField(default=0, verbose_name="Tồn kho")
    image = models.ImageField(upload_to='products/', blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ServiceOrder(models.Model):
    """
    Hóa đơn dịch vụ (Mua nước, thuê đồ).
    """
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE)
    staff_name = models.CharField(max_length=100, verbose_name="Nhân viên bán")
    total_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Tổng tiền hàng")
    created_at = models.DateTimeField(auto_now_add=True)

class ServiceOrderItem(models.Model):
    """Chi tiết hóa đơn (Mua 2 nước, 1 cầu...)"""
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=1, verbose_name="Số lượng")
    price_at_time = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá lúc bán")

