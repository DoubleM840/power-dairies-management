from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'is_active_account', 'date_joined']
    list_filter = ['role', 'is_active_account']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['date_joined']
    
    # Optimize admin queries
    list_per_page = 20
    show_full_result_count = False
    
    fieldsets = (
        (None, {
            'fields': ('user', 'role', 'is_active_account')
        }),
        ('Contact Info', {
            'fields': ('phone', 'address', 'profile_picture')
        }),
        ('System Info', {
            'fields': ('date_joined',),
            'classes': ('collapse',)
        }),
    )