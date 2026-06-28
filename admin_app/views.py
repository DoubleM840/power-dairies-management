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

from accounts.models import UserProfile
from farmer_app.models import (
    MilkRecord, Rate, Payment, Feed, FeedOrder,
    Claim, Notification, CollectorAllocation, Cow, Cart, CartItem
)

# ==================== HELPER FUNCTIONS ====================
def get_pending_milk_count():
    return MilkRecord.objects.filter(status='Pending').count()

def get_pending_collectors_count():
    return UserProfile.objects.filter(role='collector', is_approved=False).count()

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

# ==================== DASHBOARD ====================
@login_required
@admin_required
def admin_dashboard(request):
    total_users = User.objects.filter(profile__role='farmer').count()
    total_collectors = User.objects.filter(profile__role='collector', profile__is_approved=True).count()
    pending_collectors = User.objects.filter(profile__role='collector', profile__is_approved=False).count()
    
    today = timezone.now().date()
    today_milk = MilkRecord.objects.filter(date_collected=today).aggregate(total=Sum('quantity'))['total'] or 0
    month_ago = today - timedelta(days=30)
    monthly_milk = MilkRecord.objects.filter(date_collected__gte=month_ago).aggregate(total=Sum('quantity'))['total'] or 0
    
    pending_payments = Payment.objects.filter(status='Pending').count()
    pending_claims = Claim.objects.filter(status='Pending').count()
    low_stock_feeds = Feed.objects.filter(stock_quantity__lte=F('low_stock_threshold'))
    
    notifications = []
    if pending_collectors > 0:
        notifications.append({'type': 'collector', 'message': f'{pending_collectors} collector(s) awaiting approval', 'time': timezone.now()})
    
    new_claims = Claim.objects.filter(status='Pending', date_filed__gte=today - timedelta(days=1))
    for claim in new_claims:
        farmer_name = getattr(claim.farmer, 'user', claim.farmer).username
        notifications.append({'type': 'claim', 'message': f'New pending claim from {farmer_name}', 'time': claim.date_filed})
        
    new_farmers = User.objects.filter(profile__role='farmer', date_joined__gte=today - timedelta(days=1))
    for farmer in new_farmers:
        notifications.append({'type': 'farmer', 'message': f'New farmer joined: {farmer.username}', 'time': farmer.date_joined})
        
    for feed in low_stock_feeds:
        notifications.append({'type': 'stock', 'message': f'Low stock alert: {feed.name} ({feed.stock_quantity} {feed.unit} left)', 'time': timezone.now()})
        
    notifications.sort(key=lambda x: x['time'], reverse=True)

    last_7_days = []
    quantities = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        last_7_days.append(day.strftime('%Y-%m-%d'))
        qty = MilkRecord.objects.filter(date_collected=day).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'total_users': total_users, 'total_collectors': total_collectors, 'pending_collectors': pending_collectors,
        'pending_collectors_count': pending_collectors, 'today_milk': today_milk, 'monthly_milk': monthly_milk,
        'pending_payments': pending_payments, 'pending_claims': pending_claims, 'low_stock_feeds': low_stock_feeds,
        'notifications': notifications[:10], 'labels': json.dumps(last_7_days), 'quantities': json.dumps(quantities),
    }
    return render(request, 'admin_app/dashboard.html', context)

# ==================== COLLECTOR APPROVAL ====================
@login_required
@admin_required
def approve_collectors(request):
    pending_collectors = UserProfile.objects.filter(role='collector', is_approved=False).select_related('user').order_by('-date_joined')
    approved_collectors = UserProfile.objects.filter(role='collector', is_approved=True).select_related('user').order_by('-date_joined')
    
    context = {
        'pending_collectors': pending_collectors, 'approved_collectors': approved_collectors,
        'pending_collectors_count': pending_collectors.count(),
    }
    return render(request, 'admin_app/approve_collectors.html', context)

@login_required
@admin_required
def approve_collector(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id, role='collector')
    if request.method == 'POST':
        profile.is_approved = True
        profile.is_active_account = True
        profile.save()
        Notification.objects.create(user=profile.user, title='Account Approved', message='Your collector account has been approved!')
        messages.success(request, f'✓ Collector "{profile.user.username}" has been APPROVED successfully.')
    return redirect('admin_app:approve_collectors')

@login_required
@admin_required
def reject_collector(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id, role='collector')
    if request.method == 'POST':
        profile.is_approved = False
        profile.is_active_account = False
        profile.save()
        messages.warning(request, f'✗ Collector "{profile.user.username}" has been REJECTED.')
    return redirect('admin_app:approve_collectors')

# ==================== USER MANAGEMENT ====================
@login_required
@admin_required
def manage_users(request):
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    role_filter = request.GET.get('role', '')
    if role_filter: users = users.filter(profile__role=role_filter)
    return render(request, 'admin_app/manage_users.html', {'users': users, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    try:
        profile = user.profile
        profile.is_active_account = user.is_active
        profile.save()
    except UserProfile.DoesNotExist: pass
    
    status = "activated/approved" if user.is_active else "deactivated"
    messages.success(request, f'User "{user.username}" has been successfully {status}.')
    try:
        Notification.objects.create(user=user, title='Account Status Changed', message=f'Your account has been {status}.')
    except Exception: pass
    return redirect('admin_app:manage_users')

@login_required
@admin_required
def add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', '')
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        
        if not username or not email or not password or not role:
            messages.error(request, 'Username, email, password, and role are required.')
            return redirect('admin_app:add_user')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('admin_app:add_user')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('admin_app:add_user')
        
        user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name, is_active=True)
        if role == 'collector':
            user.is_staff = True
            user.save()
        
        profile = user.profile
        profile.role = role
        profile.phone = phone
        profile.address = address
        profile.is_active_account = True
        profile.is_approved = True
        profile.save()
        
        messages.success(request, f'User "{username}" created successfully as {role}.')
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

# ==================== MILK OVERVIEW & APPROVAL ====================
@login_required
@admin_required
def milk_overview(request):
    records = MilkRecord.objects.select_related('farmer', 'collector').all().order_by('-date_collected')
    today = timezone.now().date()
    last_7_days, quantities = [], []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        last_7_days.append(date.strftime('%Y-%m-%d'))
        qty = MilkRecord.objects.filter(date_collected=date).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    return render(request, 'admin_app/milk_overview.html', {'records': records, 'labels': last_7_days, 'quantities': quantities, 'pending_collectors_count': get_pending_collectors_count()})

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
    today_milk = MilkRecord.objects.filter(date_collected=today).aggregate(total=Sum('quantity'))['total'] or 0
    farmer_summary = MilkRecord.objects.values('farmer__username').annotate(total=Sum('quantity'), avg_fat=Avg('fat_content')).order_by('-total')
    return render(request, 'admin_app/milk_summary.html', {'total_milk': total_milk, 'avg_fat': avg_fat, 'today_milk': today_milk, 'farmer_summary': farmer_summary, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def milk_approval(request):
    status_filter = request.GET.get('status', 'Pending')
    records = MilkRecord.objects.select_related('farmer', 'collector').all().order_by('-date_collected', '-created_at')
    if status_filter: records = records.filter(status=status_filter)
    return render(request, 'admin_app/milk_approval.html', {'records': records, 'status_filter': status_filter, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def approve_milk_record(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            record.status = 'Approved'
            Notification.objects.create(user=record.farmer, title='Milk Record Approved', message=f'Your milk record of {record.quantity}L from {record.date_collected} has been approved.')
            messages.success(request, f'Milk record of {record.quantity}L approved successfully.')
        elif action == 'reject':
            record.status = 'Rejected'
            Notification.objects.create(user=record.farmer, title='Milk Record Rejected', message=f'Your milk record of {record.quantity}L from {record.date_collected} has been rejected.')
            messages.warning(request, f'Milk record of {record.quantity}L rejected.')
        record.save()
        return redirect('admin_app:milk_approval')
    return redirect('admin_app:milk_approval')

@login_required
@admin_required
def update_fat_content(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id)
    if request.method == 'POST':
        new_fat = request.POST.get('fat_content')
        old_fat = record.fat_content
        record.fat_content = new_fat
        record.save()
        Notification.objects.create(user=record.farmer, title='Fat Content Adjusted', message=f'Admin adjusted fat content for your milk record from {old_fat}% to {new_fat}%.')
        messages.success(request, f'Fat content updated from {old_fat}% to {new_fat}%.')
    return redirect('admin_app:milk_approval')

# ==================== RATES ====================
@login_required
@admin_required
def manage_rates(request):
    rates = Rate.objects.all().order_by('-effective_date')
    active_rate = Rate.objects.filter(is_active=True).first()
    return render(request, 'admin_app/manage_rates.html', {'rates': rates, 'active_rate': active_rate, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def add_rate(request):
    if request.method == 'POST':
        Rate.objects.filter(is_active=True).update(is_active=False)
        Rate.objects.create(fat_rate=request.POST.get('fat_rate'), commission_rate=request.POST.get('commission_rate'), effective_date=request.POST.get('effective_date'), is_active=True)
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

# ==================== PAYMENTS ====================
@login_required
@admin_required
def manage_payments(request):
    status_filter = request.GET.get('status', '')
    milk_payments = Payment.objects.select_related('user').all().order_by('-date_created')
    feed_orders = FeedOrder.objects.select_related('farmer', 'feed').all().order_by('-order_date')
    if status_filter:
        milk_payments = milk_payments.filter(status__iexact=status_filter)
        feed_orders = feed_orders.filter(status__iexact=status_filter)
    return render(request, 'admin_app/manage_payments.html', {'milk_payments': milk_payments, 'feed_orders': feed_orders, 'status_filter': status_filter, 'title': 'Manage Payments', 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def approve_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'Approved'
    payment.date_approved = timezone.now()
    payment.save()
    Notification.objects.create(user=payment.user, title='Payment Approved', message=f'Your payment of {payment.amount} has been approved.')
    messages.success(request, 'Payment approved.')
    return redirect('admin_app:manage_payments')

@login_required
@admin_required
def reject_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'Rejected'
    payment.save()
    Notification.objects.create(user=payment.user, title='Payment Rejected', message=f'Your payment of {payment.amount} has been rejected.')
    messages.success(request, 'Payment rejected.')
    return redirect('admin_app:manage_payments')

@login_required
@admin_required
def update_order_status(request, order_id):
    order = get_object_or_404(FeedOrder, id=order_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        old_status = order.status
        order.status = new_status
        order.save()
        if old_status != new_status:
            Notification.objects.create(user=order.farmer, title='Feed Order Status Updated', message=f'Your order for {order.feed.name} has been updated from {old_status} to {new_status}.')
        messages.success(request, f'Order status updated to {new_status}.')
    return redirect('admin_app:manage_payments')

# ==================== FEEDS ====================
@login_required
@admin_required
def manage_feeds(request):
    feeds = Feed.objects.all()
    low_stock = feeds.filter(stock_quantity__lte=F('low_stock_threshold'))
    for feed in low_stock:
        if not Notification.objects.filter(user=request.user, title__contains='Low Stock', message__contains=feed.name, created_at__date=timezone.now().date()).exists():
            Notification.objects.create(user=request.user, title=f'Low Stock Alert: {feed.name}', message=f'{feed.name} stock is at {feed.stock_quantity} {feed.unit}.')
    return render(request, 'admin_app/manage_feeds.html', {'feeds': feeds, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def add_feed(request):
    if request.method == 'POST':
        feed = Feed(name=request.POST.get('name'), description=request.POST.get('description'), price=request.POST.get('price'), stock_quantity=request.POST.get('stock_quantity'), low_stock_threshold=request.POST.get('low_stock_threshold', 50), unit=request.POST.get('unit', 'kg'))
        if request.FILES.get('image'): feed.image = request.FILES['image']
        feed.save()
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
        if request.FILES.get('image'): feed.image = request.FILES['image']
        elif request.POST.get('clear_image'): feed.image = None
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
    orders = FeedOrder.objects.select_related('farmer', 'feed').all().order_by('-order_date')
    total_revenue = orders.filter(status='Delivered').aggregate(total=Sum('total_price'))['total'] or 0
    pending = orders.filter(status='Pending').count()
    return render(request, 'admin_app/feed_orders_summary.html', {'orders': orders, 'total_revenue': total_revenue, 'pending': pending, 'pending_collectors_count': get_pending_collectors_count()})

# ==================== FEED ORDER MANAGEMENT ====================
@login_required
@admin_required
def view_feed_order(request, order_id):
    """View feed order details"""
    order = get_object_or_404(FeedOrder, id=order_id)
    return render(request, 'admin_app/view_feed_order.html', {
        'order': order,
        'pending_collectors_count': get_pending_collectors_count()
    })

@login_required
@admin_required
def confirm_feed_order(request, order_id):
    """Confirm/approve a feed order"""
    order = get_object_or_404(FeedOrder, id=order_id)
    order.status = 'Confirmed'
    order.save()
    
    # Notify farmer
    Notification.objects.create(
        user=order.farmer,
        title='Order Confirmed',
        message=f'Your order for {order.feed.name} has been confirmed and is being processed.'
    )
    
    messages.success(request, f'Order #{order.id} confirmed successfully.')
    return redirect('admin_app:feed_orders_summary')

@login_required
@admin_required
def reject_feed_order(request, order_id):
    """Reject a feed order"""
    order = get_object_or_404(FeedOrder, id=order_id)
    order.status = 'Cancelled'
    order.save()
    
    # Notify farmer
    Notification.objects.create(
        user=order.farmer,
        title='Order Cancelled',
        message=f'Your order for {order.feed.name} has been cancelled.'
    )
    
    messages.success(request, f'Order #{order.id} rejected.')
    return redirect('admin_app:feed_orders_summary')

# ==================== CLAIMS ====================
@login_required
@admin_required
def manage_claims(request):
    status = request.GET.get('status', '').strip()
    claims = Claim.objects.select_related('farmer', 'farmer__profile').all().order_by('-date_filed')
    if status: claims = claims.filter(status__iexact=status)
    return render(request, 'admin_app/manage_claims.html', {'claims': claims, 'title': 'Manage Claims', 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def review_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    if request.method == 'POST':
        claim.status = request.POST.get('status')
        claim.admin_response = request.POST.get('admin_response')
        if claim.status == 'Resolved': claim.date_resolved = timezone.now()
        claim.save()
        Notification.objects.create(user=claim.farmer.user, title=f'Claim Update: {claim.subject}', message=f'Your claim status has been updated to: {claim.status}.')
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
    try: Notification.objects.create(user=claim.farmer, title='Claim Approved', message=f'Your claim "{claim.subject}" has been approved.')
    except Exception: pass
    messages.success(request, 'Claim approved successfully.')
    return redirect('admin_app:manage_claims')

@login_required
@admin_required
def reject_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    claim.status = 'Rejected'
    claim.date_resolved = timezone.now()
    claim.save()
    try: Notification.objects.create(user=claim.farmer, title='Claim Rejected', message=f'Your claim "{claim.subject}" has been rejected.')
    except Exception: pass
    messages.success(request, 'Claim rejected.')
    return redirect('admin_app:manage_claims')

# ==================== COLLECTOR ALLOCATION ====================
@login_required
@admin_required
def allocate_collectors(request):
    allocations = CollectorAllocation.objects.select_related('collector', 'farmer').all()
    return render(request, 'admin_app/allocate_collectors.html', {'allocations': allocations, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def add_allocation(request):
    if request.method == 'POST':
        collector_id = request.POST.get('collector')
        farmer_id = request.POST.get('farmer')
        area = request.POST.get('area')
        collector = get_object_or_404(User, id=collector_id)
        farmer = get_object_or_404(User, id=farmer_id)
        
        existing_allocation = CollectorAllocation.objects.filter(collector=collector, farmer=farmer).first()
        if existing_allocation:
            if not existing_allocation.is_active:
                existing_allocation.is_active = True
                existing_allocation.area = area
                existing_allocation.save()
                Notification.objects.create(user=collector, title='Farmer Reassigned', message=f'You have been reassigned to collect milk from {farmer.username} in {area}.')
                Notification.objects.create(user=farmer, title='Collector Reassigned', message=f'{collector.username} has been reassigned to collect your milk.')
                messages.success(request, f'Allocation reactivated for {collector.username} → {farmer.username}.')
            else:
                messages.warning(request, f'{collector.username} is already assigned to {farmer.username} in area: {existing_allocation.area}.')
            return redirect('admin_app:allocate_collectors')
        
        CollectorAllocation.objects.create(collector=collector, farmer=farmer, area=area, is_active=True)
        Notification.objects.create(user=collector, title='New Farmer Assigned', message=f'You have been assigned to collect milk from {farmer.username} in {area}.')
        Notification.objects.create(user=farmer, title='Collector Assigned', message=f'{collector.username} has been assigned to collect your milk.')
        messages.success(request, f'Collector {collector.username} allocated to {farmer.username} successfully.')
        return redirect('admin_app:allocate_collectors')
    
    collectors = User.objects.filter(profile__role='collector', profile__is_approved=True)
    farmers = User.objects.filter(profile__role='farmer')
    return render(request, 'admin_app/add_allocation.html', {'collectors': collectors, 'farmers': farmers, 'pending_collectors_count': get_pending_collectors_count()})

@login_required
@admin_required
def delete_allocation(request, allocation_id):
    allocation = get_object_or_404(CollectorAllocation, id=allocation_id)
    if request.method == 'POST':
        allocation.delete()
        messages.success(request, 'Allocation deleted.')
    return redirect('admin_app:allocate_collectors')

# ==================== LIVESTOCK OVERSIGHT ====================
@login_required
@admin_required
def all_livestock(request):
    farmer_filter = request.GET.get('farmer', '')
    breed_filter = request.GET.get('breed', '')
    health_filter = request.GET.get('health', '')
    cows = Cow.objects.select_related('farmer').all().order_by('-date_added')
    if farmer_filter: cows = cows.filter(farmer__id=farmer_filter)
    if breed_filter: cows = cows.filter(breed_type=breed_filter)
    if health_filter: cows = cows.filter(health_status=health_filter)
    
    farmers = User.objects.filter(profile__role='farmer').order_by('username')
    breeds = Cow.objects.values_list('breed_type', flat=True).distinct()
    
    context = {
        'cows': cows, 'farmers': farmers, 'breeds': breeds,
        'total_cows': cows.count(), 'healthy_count': cows.filter(health_status='Healthy').count(),
        'sick_count': cows.filter(health_status='Sick').count(), 'treatment_count': cows.filter(health_status='Under Treatment').count(),
        'farmer_filter': farmer_filter, 'breed_filter': breed_filter, 'health_filter': health_filter,
        'pending_collectors_count': get_pending_collectors_count(),
    }
    return render(request, 'admin_app/all_livestock.html', context)

@login_required
@admin_required
def livestock_health(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id)
    records = cow.health_records.all().order_by('-date')
    return render(request, 'admin_app/livestock_health.html', {'cow': cow, 'records': records, 'pending_collectors_count': get_pending_collectors_count()})

# ==================== NOTIFICATIONS ====================
@login_required
@admin_required
def notifications(request):
    user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    today_notifications = user_notifications.filter(created_at__date=timezone.now().date()).count()
    return render(request, 'admin_app/notifications.html', {'notifications': user_notifications, 'today_notifications': today_notifications, 'pending_collectors_count': get_pending_collectors_count()})