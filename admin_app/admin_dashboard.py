from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import reverse
from farmer_app.models import MilkRecord, Cow, Payment, Claim, Feed
from accounts.models import UserProfile
from django.db.models import Sum, Count


class CustomAdminSite(AdminSite):
    site_header = 'Power Dairies Administration'
    site_title = 'Power Dairies Admin'
    index_title = 'Dashboard Overview'
    
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Add custom stats
        extra_context['total_farmers'] = UserProfile.objects.filter(role='farmer').count()
        extra_context['total_collectors'] = UserProfile.objects.filter(role='collector', is_approved=True).count()
        extra_context['pending_collectors'] = UserProfile.objects.filter(role='collector', is_approved=False).count()
        extra_context['total_cows'] = Cow.objects.count()
        extra_context['today_milk'] = MilkRecord.objects.filter(
            date_collected=__import__('django.utils.timezone', fromlist=['now']).now().date()
        ).aggregate(total=Sum('quantity'))['total'] or 0
        extra_context['pending_payments'] = Payment.objects.filter(status='Pending').count()
        extra_context['pending_claims'] = Claim.objects.filter(status='Pending').count()
        extra_context['low_stock_feeds'] = Feed.objects.filter(
            stock_quantity__lte=__import__('django.db.models', fromlist=['F']).F('low_stock_threshold')
        ).count()
        
        return super().index(request, extra_context)


# Create custom admin site instance
custom_admin_site = CustomAdminSite(name='custom_admin')