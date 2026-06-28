from django.contrib import admin
from django.utils import timezone
from .models import (
    Feed, Cow, MilkRecord, Payment, Claim, Notification, 
    FeedOrder, Cart, CartItem, Rate, CollectorAllocation, HealthRecord
)

# Helper function to safely create notifications
def send_notification(user, title, message):
    try:
        Notification.objects.create(user=user, title=title, message=message)
    except Exception:
        pass

# 1. CLEAR OLD REGISTRATIONS (The Nuclear Fix)
models_to_clear = [Feed, Cow, MilkRecord, Payment, Claim, Notification, 
                   FeedOrder, Cart, CartItem, Rate, CollectorAllocation, HealthRecord]

for model in models_to_clear:
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass

# 2. REGISTER WITH SYNC LOGIC

@admin.register(Cow)
class CowAdmin(admin.ModelAdmin):
    list_display = ('tag', 'name', 'breed_type', 'farmer', 'health_status', 'date_added')
    list_filter = ('breed_type', 'health_status')
    search_fields = ('tag', 'name', 'farmer__username')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:  # Only on creation
            send_notification(obj.farmer, 'Livestock Added', f'Cow {obj.tag} ({obj.breed_type}) was added to your profile by Admin.')

@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ('cow', 'date', 'vet_name', 'description')
    list_filter = ('date',)

@admin.register(MilkRecord)
class MilkRecordAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'collector', 'quantity', 'fat_content', 'date_collected', 'status')
    list_filter = ('status', 'date_collected')
    list_editable = ('status',)
    search_fields = ('farmer__username', 'collector__username')
    
    actions = ['approve_records', 'reject_records']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and obj.status in ['Approved', 'Rejected']:
            send_notification(obj.farmer, f'Milk Record {obj.status}', 
                              f'Your milk record of {obj.quantity}L on {obj.date_collected} has been {obj.status.lower()}.')

    def approve_records(self, request, queryset):
        for record in queryset.filter(status='Pending'):
            record.status = 'Approved'
            record.save()
            send_notification(record.farmer, 'Milk Record Approved', f'Your record of {record.quantity}L was approved via Admin.')
        self.message_user(request, f'{queryset.count()} record(s) approved.')
    approve_records.short_description = "Approve selected milk records"

    def reject_records(self, request, queryset):
        for record in queryset.filter(status='Pending'):
            record.status = 'Rejected'
            record.save()
            send_notification(record.farmer, 'Milk Record Rejected', f'Your record of {record.quantity}L was rejected via Admin.')
        self.message_user(request, f'{queryset.count()} record(s) rejected.')
    reject_records.short_description = "Reject selected milk records"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'date_created', 'payment_type')
    list_filter = ('status', 'payment_type')
    list_editable = ('status',)
    
    actions = ['approve_payments', 'reject_payments']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and obj.status in ['Approved', 'Rejected']:
            send_notification(obj.user, f'Payment {obj.status}', f'Your payment of {obj.amount} has been {obj.status.lower()}.')

    def approve_payments(self, request, queryset):
        for payment in queryset.filter(status='Pending'):
            payment.status = 'Approved'
            payment.date_approved = timezone.now()
            payment.save()
            send_notification(payment.user, 'Payment Approved', f'Your payment of {payment.amount} was approved.')
        self.message_user(request, f'{queryset.count()} payment(s) approved.')
    approve_payments.short_description = "Approve selected payments"

    def reject_payments(self, request, queryset):
        for payment in queryset.filter(status='Pending'):
            payment.status = 'Rejected'
            payment.save()
            send_notification(payment.user, 'Payment Rejected', f'Your payment of {payment.amount} was rejected.')
        self.message_user(request, f'{queryset.count()} payment(s) rejected.')
    reject_payments.short_description = "Reject selected payments"

@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_quantity', 'unit', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)
    fieldsets = (
        ('Feed Information', {'fields': ('name', 'category', 'description', 'price', 'unit')}),
        ('Stock Management', {'fields': ('stock_quantity', 'low_stock_threshold', 'is_active')}),
        ('Media', {'fields': ('image',)}),
    )

@admin.register(FeedOrder)
class FeedOrderAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'feed', 'quantity', 'total_price', 'status', 'order_date')
    list_filter = ('status',)

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'subject', 'status', 'date_filed')
    list_filter = ('status',)
    list_editable = ('status',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)

# Register remaining models simply
admin.site.register(Rate)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(CollectorAllocation)