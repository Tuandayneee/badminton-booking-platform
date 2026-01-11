from django.contrib import admin
from users.models import PartnerProfile, User
from django.contrib.auth.admin import UserAdmin


class PartnerProfileInline(admin.StackedInline):
    model = PartnerProfile
    can_delete = False
    verbose_name_plural = 'Hồ sơ Đối tác'

@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'phone_number')
    list_filter = ('role',) 
    inlines = [PartnerProfileInline]

@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('business_name', 'user__username', 'tax_id')
    actions = ['approve_partners']

    
    @admin.action(description='Duyệt các đối tác đã chọn')
    def approve_partners(self, request, queryset):
        queryset.update(is_verified=True)
    
