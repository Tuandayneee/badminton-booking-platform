from django.db import models
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from django.db.models.signals import post_save
class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Khách hàng'
        PARTNER = 'partner', 'Đối tác'
        ADMIN = 'admin', 'Quản trị viên'
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    

    def __str__(self):
        return self.username
    
   
    

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    class Ranking (models.TextChoices):
        BRONZE = 'bronze', 'Hạng Đồng'
        SILVER = 'silver', 'Hạng Bạc'
        GOLD = 'gold', 'Hạng Vàng'
        DIAMOND = 'diamond', 'Hạng Kim Cương'
    rank = models.CharField(max_length=10, choices=Ranking.choices, default=Ranking.BRONZE)
    points = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.get_rank_display()}"
    def update_rank(self):
        if self.points >= 1000:
            self.rank = self.Rank.DIAMOND
        elif self.points >= 500:
            self.rank = self.Rank.GOLD
        elif self.points >= 200:
            self.rank = self.Rank.SILVER
        else:
            self.rank = self.Rank.BRONZE
        self.save()


class PartnerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='partner_profile')
    business_name = models.CharField(max_length=200, verbose_name="Tên đơn vị kinh doanh")
    business_address = models.CharField(max_length=255, verbose_name="Địa chỉ kinh doanh")
    
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="Tên ngân hàng")
    bank_account_number = models.CharField(max_length=30, blank=True, verbose_name="Số tài khoản")
    bank_account_owner = models.CharField(max_length=100, blank=True, verbose_name="Tên chủ tài khoản")
    contact_person = models.CharField(max_length=100, verbose_name="Người đại diện", default="")
    is_verified = models.BooleanField(default=False, verbose_name="Đã xác minh")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Partner: {self.business_name} ({self.user.username})"
    

@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    if created and instance.role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(user=instance)