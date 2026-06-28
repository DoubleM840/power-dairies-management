from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile
# Import notification model from farmer_app to trigger sync notifications
from farmer_app.models import Notification 

def send_notification(user, title, message):
    try:
        Notification.objects.create(user=user, title=title, message=message)
    except Exception:
        pass

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    # Added 'is_approved' so you can approve collectors directly from the User page
    fields = ('role', 'is_approved', 'is_active_account', 'phone', 'address', 'farmer_number') 
    readonly_fields = ('farmer_number',)

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'profile__role', 'profile__is_approved')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    # Add bulk actions for approving collectors
    actions = ['approve_collectors_bulk', 'deactivate_users']

    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except:
            return 'N/A'
    get_role.short_description = 'Role'

    def approve_collectors_bulk(self, request, queryset):
        """Bulk approve collectors and notify them"""
        count = 0
        for user in queryset:
            try:
                if user.profile.role == 'collector' and not user.profile.is_approved:
                    user.profile.is_approved = True
                    user.profile.is_active_account = True
                    user.profile.save()
                    send_notification(user, 'Account Approved', 'Your collector account has been approved by Admin via Django Admin.')
                    count += 1
            except UserProfile.DoesNotExist:
                pass
        self.message_user(request, f'{count} collector(s) approved and notified.')
    approve_collectors_bulk.short_description = "Approve selected Collectors"

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated successfully.')
    deactivate_users.short_description = 'Deactivate selected users'

# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'is_approved', 'is_active_account', 'date_joined']
    list_filter = ['role', 'is_approved', 'is_active_account']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['date_joined', 'farmer_number']

# Admin site customization
admin.site.site_header = "Power Dairies Administration"
admin.site.site_title = "Power Dairies Admin"
admin.site.index_title = "Dashboard"