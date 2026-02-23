from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PartnerProfile, CustomerProfile, StaffProfile
from .tasks import send_register_confirmation_email


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



class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_username', 'contact_person', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('contact_person', 'user__username', 'user__email', 'user__full_name')
    
    actions = ['approve_partners', 'reject_partners']

    @admin.display(description='Tài khoản (Username)', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username

    @admin.action(description='Duyệt các đối tác đã chọn')
    def approve_partners(self, request, queryset):
        count = 0
        for profile in queryset:
            try:
                send_register_confirmation_email.delay(
                    username=profile.user.username,
                    email=profile.user.email,
                    phone_number=profile.user.phone_number or '',
                    bank_name=profile.bank_name or '',
                    bank_account_number=profile.bank_account_number or '',
                    bank_account_owner=profile.bank_account_owner or '',
                    contact_person=profile.contact_person or ''
                )
                count += 1
            except Exception as e:
                self.message_user(request, f"Lỗi gửi email cho {profile.user.email}: {e}", level='error')
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"Đã duyệt {updated} đối tác và gửi {count} email thành công.")

    @admin.action(description='Hủy xác minh đối tác')
    def reject_partners(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"Đã hủy xác minh {updated} đối tác.")

admin.site.register(PartnerProfile, PartnerProfileAdmin)
@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'points')
    list_filter = ('rank',)
    search_fields = ('user__username', 'user__email')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'center', 'position', 'is_active', 'created_at')
    list_filter = ('is_active', 'center')
    search_fields = ('user__username', 'user__email', 'user__full_name', 'position')
    raw_id_fields = ('user', 'center')
