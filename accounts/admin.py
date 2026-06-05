from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'is_active_account', 'date_joined']
    list_filter = ['role', 'is_active_account']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['date_joined', 'farmer_number']
    
    # Optimize admin queries
    list_per_page = 20
    show_full_result_count = False
    
    fieldsets = (
        (None, {
            'fields': ('user', 'role', 'is_active_account', 'farmer_number')
        }),
        ('Contact Info', {
            'fields': ('phone', 'address', 'profile_picture')
        }),
        ('System Info', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )


# Inline profile for User
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('role', 'farmer_number', 'phone', 'address', 'is_active_account', 'profile_picture')
    readonly_fields = ('farmer_number',)


# Custom User Admin
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'profile__role', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except:
            return 'N/A'
    get_role.short_description = 'Role'
    
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated successfully.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated successfully.')
    deactivate_users.short_description = 'Deactivate selected users'


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Admin site customization
admin.site.site_header = "Power Dairies Administration"
admin.site.site_title = "Power Dairies Admin"
admin.site.index_title = "Dashboard"