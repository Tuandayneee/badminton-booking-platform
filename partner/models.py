import datetime
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User, PartnerProfile 
from django.utils.translation import gettext_lazy as _
import uuid

class Amenity(models.Model):
    name = models.CharField(max_length=50, verbose_name="Tên tiện ích")
    
    def __str__(self):
        return self.name
    
class BadmintonCenter(models.Model):
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False 
    )
    
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='centers', verbose_name="Đối tác")
    name = models.CharField(max_length=100, verbose_name="Tên trung tâm")
    image = models.ImageField(upload_to='center_images/', blank=True, verbose_name="Ảnh đại diện")
   
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
    class TypeCourt(models.TextChoices):
        WOODEN = 'wooden', 'Sàn gỗ'
        CARPET = 'carpet', 'Sàn thảm'
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE, related_name='courts')
    name = models.CharField(max_length=50, verbose_name="Tên sân") 
    type_court = models.CharField(max_length=20, choices=TypeCourt.choices,default=TypeCourt.WOODEN,  verbose_name="Loại sân")
    base_price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá cơ bản/giờ")
    golden_price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá giờ vàng/giờ", null=True, blank=True)
    golden_start_time = models.TimeField(verbose_name="Bắt đầu giờ vàng", null=True, blank=True)
    golden_end_time = models.TimeField(verbose_name="Kết thúc giờ vàng", null=True, blank=True)  
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    def __str__(self):
        return f"{self.center.name} - {self.name}"
    def get_price_at_time(self, check_time_str):
        """Hàm tính giá tiền dựa vào giờ"""
        if not self.golden_price_per_hour or not self.golden_start_time:
            return self.base_price_per_hour
        check_time = datetime.datetime.strptime(check_time_str, "%H:%M").time()
        if self.golden_start_time <= check_time < self.golden_end_time:
            return self.golden_price_per_hour
            
        return self.base_price_per_hour
class PriceRule(models.Model):
    center = models.ForeignKey(BadmintonCenter, on_delete=models.CASCADE, related_name='price_rules')
    name = models.CharField(max_length=100, verbose_name="Tên khung giờ")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu")
    end_time = models.TimeField(verbose_name="Giờ kết thúc")
    days_of_week = models.JSONField(default=list, verbose_name="Ngày trong tuần áp dụng (0=Thứ 2, 6=Chủ nhật)")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá/giờ")
    priority = models.IntegerField(default=1, verbose_name="Độ ưu tiên")
    


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

