from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PartnerProfile, CustomerProfile



class PartnerProfileInline(admin.StackedInline):
    model = PartnerProfile
    can_delete = False
    verbose_name_plural = 'Hồ sơ Đối tác (Partner)'
    fk_name = 'user'
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        return formset

class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    verbose_name_plural = 'Hồ sơ Khách hàng (Customer)'
    fk_name = 'user'



@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    # Hiển thị danh sách
    list_display = ('username', 'email', 'full_name', 'role', 'phone_number', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone_number')
    
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Thông tin bổ sung', {'fields': ('role', 'phone_number')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Thông tin bổ sung', {'fields': ('role', 'phone_number', 'email')}),
    )
    
    inlines = [PartnerProfileInline, CustomerProfileInline]



@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'business_name', 'get_username', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('business_name', 'user__username', 'user__email', 'contact_person')
    
    actions = ['approve_partners', 'reject_partners']

   
    @admin.display(description='Tài khoản', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username

    @admin.action(description='✅ Duyệt các đối tác đã chọn')
    def approve_partners(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"Đã duyệt {updated} đối tác thành công.")

    @admin.action(description='🚫 Hủy xác minh đối tác')
    def reject_partners(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"Đã hủy xác minh {updated} đối tác.")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'points')
    list_filter = ('rank',)
    search_fields = ('user__username', 'user__email')