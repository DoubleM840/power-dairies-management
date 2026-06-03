import json
from functools import wraps
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Avg, F
from django.http import JsonResponse

from farmer_app.models import (
    UserProfile, MilkRecord, Rate, Payment, Feed, FeedOrder,
    Claim, Notification, CollectorAllocation, Cow, Cart, CartItem
)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        try:
            if request.user.profile.role != 'admin':
                messages.error(request, 'Access denied. Admin only.')
                return redirect('accounts:login')
        except UserProfile.DoesNotExist:
            messages.error(request, 'Access denied.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@admin_required
def admin_dashboard(request):
    total_users = User.objects.filter(profile__role='farmer').count()
    total_collectors = User.objects.filter(profile__role='collector').count()
    today = timezone.now().date()
    
    today_milk = MilkRecord.objects.filter(date_collected=today).aggregate(
        total=Sum('quantity'))['total'] or 0
    
    pending_payments = Payment.objects.filter(status='Pending').count()
    pending_claims = Claim.objects.filter(status='Pending').count()
    
    # Get low stock feeds for both the banner and the quick stats
    low_stock_feeds = Feed.objects.filter(stock_quantity__lte=F('low_stock_threshold'))
    
    # --- NOTIFICATIONS LOGIC ---
    notifications = []
    
    # 1. New Claims (last 24 hours) 
    # FIXED: Changed 'created_at' to 'date_filed' to match your Claim model
    new_claims = Claim.objects.filter(status='Pending', date_filed__gte=today - timedelta(days=1))
    for claim in new_claims:
        # Safely get the username whether farmer is a User or a Profile with a User relation
        farmer_name = getattr(claim.farmer, 'user', claim.farmer).username
        notifications.append({
            'type': 'claim',
            'message': f'New pending claim from {farmer_name}',
            'time': claim.date_filed
        })
    
    # 2. New Farmers (last 24 hours)
    new_farmers = User.objects.filter(profile__role='farmer', date_joined__gte=today - timedelta(days=1))
    for farmer in new_farmers:
        notifications.append({
            'type': 'farmer',
            'message': f'New farmer joined: {farmer.username}',
            'time': farmer.date_joined
        })
    
    # 3. Low Stock Alerts
    for feed in low_stock_feeds:
        notifications.append({
            'type': 'stock',
            'message': f'Low stock alert: {feed.name} ({feed.stock_quantity} {feed.unit} left)',
            'time': timezone.now()
        })
    
    # Sort notifications by time (newest first)
    notifications.sort(key=lambda x: x['time'], reverse=True)

    # Milk Trend Chart Data
    last_7_days = []
    quantities = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        last_7_days.append(day.strftime('%Y-%m-%d'))
        qty = MilkRecord.objects.filter(date_collected=day).aggregate(
            total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'total_users': total_users,
        'total_collectors': total_collectors,
        'today_milk': today_milk,
        'pending_payments': pending_payments,
        'pending_claims': pending_claims,
        'low_stock_feeds': low_stock_feeds, # Passed directly for the template loop
        'notifications': notifications[:10],
        'labels': json.dumps(last_7_days),
        'quantities': json.dumps(quantities),
    }
    return render(request, 'admin_app/dashboard.html', context)


# ==================== USER MANAGEMENT ====================
@login_required
@admin_required
def manage_users(request):
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(profile__role=role_filter)
    return render(request, 'admin_app/manage_users.html', {'users': users})


@login_required
@admin_required
def toggle_user_status(request, user_id):
    """Activate or Deactivate a user account"""
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f'User "{user.username}" has been successfully {status}.')
    return redirect('admin_app:manage_users')


@login_required
@admin_required
def add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('admin_app:add_user')
        
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name
        )
        UserProfile.objects.create(user=user, role=role, phone=phone, address=address)
        messages.success(request, f'User {username} created successfully.')
        return redirect('admin_app:manage_users')
    return render(request, 'admin_app/add_user.html')


@login_required
@admin_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        
        profile = user.profile
        profile.phone = request.POST.get('phone')
        profile.address = request.POST.get('address')
        profile.role = request.POST.get('role')
        profile.save()
        messages.success(request, 'User updated successfully.')
        return redirect('admin_app:manage_users')
    return render(request, 'admin_app/edit_user.html', {'edit_user': user})


@login_required
@admin_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully.')
    return redirect('admin_app:manage_users')


# ==================== MILK OVERVIEW ====================
@login_required
@admin_required
def milk_overview(request):
    records = MilkRecord.objects.select_related('farmer', 'collector').all().order_by('-date_collected')
    today = timezone.now().date()
    
    last_7_days = []
    quantities = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        last_7_days.append(date.strftime('%Y-%m-%d'))
        qty = MilkRecord.objects.filter(date_collected=date).aggregate(
            total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'records': records,
        'labels': last_7_days,
        'quantities': quantities,
    }
    return render(request, 'admin_app/milk_overview.html', context)


@login_required
@admin_required
def edit_milk_record(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id)
    if request.method == 'POST':
        record.quantity = request.POST.get('quantity')
        record.fat_content = request.POST.get('fat_content')
        record.status = request.POST.get('status')
        record.notes = request.POST.get('notes')
        record.save()
        messages.success(request, 'Milk record updated successfully.')
        return redirect('admin_app:milk_overview')
    return render(request, 'admin_app/edit_milk_record.html', {'record': record})


@login_required
@admin_required
def milk_summary(request):
    today = timezone.now().date()
    total_milk = MilkRecord.objects.aggregate(total=Sum('quantity'))['total'] or 0
    avg_fat = MilkRecord.objects.aggregate(avg=Avg('fat_content'))['avg'] or 0
    today_milk = MilkRecord.objects.filter(date_collected=today).aggregate(
        total=Sum('quantity'))['total'] or 0
    
    farmer_summary = MilkRecord.objects.values('farmer__username').annotate(
        total=Sum('quantity'), avg_fat=Avg('fat_content')
    ).order_by('-total')
    
    context = {
        'total_milk': total_milk,
        'avg_fat': avg_fat,
        'today_milk': today_milk,
        'farmer_summary': farmer_summary,
    }
    return render(request, 'admin_app/milk_summary.html', context)


# ==================== RATES ====================
@login_required
@admin_required
def manage_rates(request):
    rates = Rate.objects.all().order_by('-effective_date')
    active_rate = Rate.objects.filter(is_active=True).first()
    return render(request, 'admin_app/manage_rates.html', {'rates': rates, 'active_rate': active_rate})


@login_required
@admin_required
def add_rate(request):
    if request.method == 'POST':
        fat_rate = request.POST.get('fat_rate')
        commission_rate = request.POST.get('commission_rate')
        effective_date = request.POST.get('effective_date')
        
        Rate.objects.filter(is_active=True).update(is_active=False)
        Rate.objects.create(
            fat_rate=fat_rate,
            commission_rate=commission_rate,
            effective_date=effective_date,
            is_active=True
        )
        messages.success(request, 'New rate added successfully.')
        return redirect('admin_app:manage_rates')
    return render(request, 'admin_app/add_rate.html')


@login_required
@admin_required
def edit_rate(request, rate_id):
    rate = get_object_or_404(Rate, id=rate_id)
    if request.method == 'POST':
        rate.fat_rate = request.POST.get('fat_rate')
        rate.commission_rate = request.POST.get('commission_rate')
        rate.effective_date = request.POST.get('effective_date')
        rate.save()
        messages.success(request, 'Rate updated successfully.')
        return redirect('admin_app:manage_rates')
    return render(request, 'admin_app/edit_rate.html', {'rate': rate})


# ==================== PAYMENTS (SEPARATED) ====================
@login_required
@admin_required
def manage_payments(request):
    """Displays both Milk Payments and Feed Orders separately for neatness"""
    status_filter = request.GET.get('status', '')
    
    # 1. Milk Payments
    milk_payments = Payment.objects.select_related('user').all().order_by('-date_created')
    if status_filter:
        milk_payments = milk_payments.filter(status__iexact=status_filter)
        
    # 2. Feed Orders
    feed_orders = FeedOrder.objects.select_related('farmer', 'feed').all().order_by('-order_date')
    if status_filter:
        feed_orders = feed_orders.filter(status__iexact=status_filter)
        
    return render(request, 'admin_app/manage_payments.html', {
        'milk_payments': milk_payments,
        'feed_orders': feed_orders,
        'status_filter': status_filter,
        'title': 'Manage Payments'
    })


@login_required
@admin_required
def approve_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'Approved'
    payment.date_approved = timezone.now()
    payment.save()
    
    Notification.objects.create(
        user=payment.user,
        title='Payment Approved',
        message=f'Your payment of {payment.amount} has been approved.'
    )
    messages.success(request, 'Payment approved.')
    return redirect('admin_app:manage_payments')


@login_required
@admin_required
def reject_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'Rejected'
    payment.save()
    
    Notification.objects.create(
        user=payment.user,
        title='Payment Rejected',
        message=f'Your payment of {payment.amount} has been rejected.'
    )
    messages.success(request, 'Payment rejected.')
    return redirect('admin_app:manage_payments')


# ==================== FEEDS ====================
@login_required
@admin_required
def manage_feeds(request):
    feeds = Feed.objects.all()
    low_stock = feeds.filter(stock_quantity__lte=F('low_stock_threshold'))
    for feed in low_stock:
        if not Notification.objects.filter(
            user=request.user, title__contains='Low Stock',
            message__contains=feed.name, created_at__date=timezone.now().date()
        ).exists():
            Notification.objects.create(
                user=request.user,
                title=f'Low Stock Alert: {feed.name}',
                message=f'{feed.name} stock is at {feed.stock_quantity} {feed.unit}. Threshold is {feed.low_stock_threshold}.'
            )
    return render(request, 'admin_app/manage_feeds.html', {'feeds': feeds})


@login_required
@admin_required
def add_feed(request):
    if request.method == 'POST':
        Feed.objects.create(
            name=request.POST.get('name'),
            description=request.POST.get('description'),
            price=request.POST.get('price'),
            stock_quantity=request.POST.get('stock_quantity'),
            low_stock_threshold=request.POST.get('low_stock_threshold', 50),
            unit=request.POST.get('unit', 'kg'),
        )
        messages.success(request, 'Feed added successfully.')
        return redirect('admin_app:manage_feeds')
    return render(request, 'admin_app/add_feed.html')


@login_required
@admin_required
def edit_feed(request, feed_id):
    feed = get_object_or_404(Feed, id=feed_id)
    if request.method == 'POST':
        feed.name = request.POST.get('name')
        feed.description = request.POST.get('description')
        feed.price = request.POST.get('price')
        feed.stock_quantity = request.POST.get('stock_quantity')
        feed.low_stock_threshold = request.POST.get('low_stock_threshold')
        feed.unit = request.POST.get('unit')
        feed.save()
        messages.success(request, 'Feed updated successfully.')
        return redirect('admin_app:manage_feeds')
    return render(request, 'admin_app/edit_feed.html', {'feed': feed})


@login_required
@admin_required
def delete_feed(request, feed_id):
    feed = get_object_or_404(Feed, id=feed_id)
    if request.method == 'POST':
        feed.delete()
        messages.success(request, 'Feed deleted successfully.')
    return redirect('admin_app:manage_feeds')


@login_required
@admin_required
def feed_orders_summary(request):
    """Dedicated summary page for Feed Orders"""
    # FIXED: Changed 'created_at' to 'order_date' to match your FeedOrder model
    orders = FeedOrder.objects.select_related('farmer', 'feed').all().order_by('-order_date')
    
    total_revenue = orders.filter(status='Delivered').aggregate(
        total=Sum('total_price'))['total'] or 0
    pending = orders.filter(status='Pending').count()
    
    return render(request, 'admin_app/feed_orders_summary.html', {
        'orders': orders, 
        'total_revenue': total_revenue, 
        'pending': pending
    })


# ==================== CLAIMS ====================
@login_required
@admin_required
def manage_claims(request):
    """Strictly queries Claim model"""
    status = request.GET.get('status', '').strip()
    
    # FIXED: Use 'date_filed' instead of 'created_at'
    claims = Claim.objects.select_related('farmer', 'farmer__profile').all().order_by('-date_filed')
    
    if status:
        claims = claims.filter(status__iexact=status)
        
    return render(request, 'admin_app/manage_claims.html', {
        'claims': claims,
        'title': 'Manage Claims',
    })


@login_required
@admin_required
def review_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    if request.method == 'POST':
        claim.status = request.POST.get('status')
        claim.admin_response = request.POST.get('admin_response')
        if claim.status == 'Resolved':
            claim.date_resolved = timezone.now()
        claim.save()
        
        Notification.objects.create(
            user=claim.farmer.user,
            title=f'Claim Update: {claim.subject}',
            message=f'Your claim status has been updated to: {claim.status}. Response: {claim.admin_response}'
        )
        messages.success(request, 'Claim reviewed successfully.')
        return redirect('admin_app:manage_claims')
    return render(request, 'admin_app/review_claim.html', {'claim': claim})

@login_required
@admin_required
def approve_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    claim.status = 'Approved'
    claim.date_resolved = timezone.now()
    claim.save()
    
    # Notify the farmer (claim.farmer is the User object directly)
    try:
        Notification.objects.create(
            user=claim.farmer,
            title='Claim Approved',
            message=f'Your claim "{claim.subject}" has been approved.'
        )
    except Exception:
        pass  # Prevents crash if notification creation fails
        
    messages.success(request, 'Claim approved successfully.')
    return redirect('admin_app:manage_claims')


@login_required
@admin_required
def reject_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    claim.status = 'Rejected'
    claim.date_resolved = timezone.now()
    claim.save()
    
    # Notify the farmer
    try:
        Notification.objects.create(
            user=claim.farmer,
            title='Claim Rejected',
            message=f'Your claim "{claim.subject}" has been rejected.'
        )
    except Exception:
        pass
        
    messages.success(request, 'Claim rejected.')
    return redirect('admin_app:manage_claims')

# ==================== COLLECTOR ALLOCATION ====================
@login_required
@admin_required
def allocate_collectors(request):
    allocations = CollectorAllocation.objects.select_related('collector', 'farmer').all()
    return render(request, 'admin_app/allocate_collectors.html', {'allocations': allocations})


@login_required
@admin_required
def add_allocation(request):
    if request.method == 'POST':
        collector_id = request.POST.get('collector')
        farmer_id = request.POST.get('farmer')
        area = request.POST.get('area')
        
        collector = get_object_or_404(User, id=collector_id)
        farmer = get_object_or_404(User, id=farmer_id)
        
        CollectorAllocation.objects.create(
            collector=collector, farmer=farmer, area=area, is_active=True
        )
        
        Notification.objects.create(
            user=collector,
            title='New Farmer Assigned',
            message=f'You have been assigned to collect milk from {farmer.username} in {area}.'
        )
        Notification.objects.create(
            user=farmer,
            title='Collector Assigned',
            message=f'{collector.username} has been assigned to collect your milk.'
        )
        
        messages.success(request, 'Collector allocated successfully.')
        return redirect('admin_app:allocate_collectors')
    
    collectors = User.objects.filter(profile__role='collector')
    farmers = User.objects.filter(profile__role='farmer')
    return render(request, 'admin_app/add_allocation.html', {
        'collectors': collectors, 'farmers': farmers
    })


@login_required
@admin_required
def delete_allocation(request, allocation_id):
    allocation = get_object_or_404(CollectorAllocation, id=allocation_id)
    if request.method == 'POST':
        allocation.delete()
        messages.success(request, 'Allocation deleted.')
    return redirect('admin_app:allocate_collectors')

# ==================== COLLECTOR VIEWS (FOR NOTIFICATIONS) ====================
@login_required
@admin_required
def notifications(request):
    """Display all notifications for the admin"""
    # Get all notifications for the current user
    user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Count today's notifications
    today = timezone.now().date()
    today_notifications = user_notifications.filter(created_at__date=today).count()
    
    context = {
        'notifications': user_notifications,
        'today_notifications': today_notifications,
    }
    return render(request, 'admin_app/notifications.html', context)