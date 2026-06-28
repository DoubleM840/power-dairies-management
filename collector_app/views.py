from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg
import json
from datetime import timedelta 
from farmer_app.models import (
    UserProfile, MilkRecord, Payment, Notification, CollectorAllocation, User
)
from functools import wraps


def collector_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')  # FIXED: Added 'accounts:' namespace
        try:
            if request.user.profile.role != 'collector':  # FIXED: Changed farmer_profile to profile
                messages.error(request, 'Access denied. Collectors only.')
                return redirect('accounts:login')
        except UserProfile.DoesNotExist:
            messages.error(request, 'Access denied.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def collector_dashboard(request):
    """Main dashboard for the collector"""
    today = timezone.now().date()
    
    # Get allocated farmers
    allocations = CollectorAllocation.objects.filter(
        collector=request.user, 
        is_active=True
    ).select_related('farmer')
    
    allocated_farmers_count = allocations.count()
    
    # Stats
    today_milk = MilkRecord.objects.filter(
        collector=request.user, date_collected=today
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    today_collections_count = MilkRecord.objects.filter(
        collector=request.user, date_collected=today
    ).count()
    
    total_milk = MilkRecord.objects.filter(
        collector=request.user
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    total_farmers_visited = MilkRecord.objects.filter(
        collector=request.user
    ).values('farmer').distinct().count()
    
    pending_records = MilkRecord.objects.filter(
        collector=request.user, status='Pending'
    ).count()
    
    approved_records = MilkRecord.objects.filter(
        collector=request.user, status='Approved'
    ).count()
    
    # Calculate total payments for today's collections
    today_payments = Payment.objects.filter(
        user=request.user,
        date_created__date=today,
        status='Completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent collections
    recent_collections = MilkRecord.objects.filter(
        collector=request.user
    ).select_related('farmer').order_by('-date_collected')[:10]
    
    # Chart data - last 7 days
    labels = []
    quantities = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        qty = MilkRecord.objects.filter(
            collector=request.user, date_collected=date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'today_milk': today_milk,
        'today_collections_count': today_collections_count,
        'total_milk': total_milk,
        'total_farmers_visited': total_farmers_visited,
        'allocated_farmers_count': allocated_farmers_count,
        'pending_records': pending_records,
        'approved_records': approved_records,
        'today_payments': today_payments,
        'recent_collections': recent_collections,
        'labels': json.dumps(labels),
        'quantities': json.dumps(quantities),
    }
    return render(request, 'collector_app/dashboard.html', context)


@login_required
def collect_milk(request):
    if request.method == 'POST':
        farmer_id = request.POST.get('farmer')
        quantity = request.POST.get('quantity')
        date_collected = request.POST.get('date_collected')
        notes = request.POST.get('notes', '')
        
        fat_content = 3.5  # Standard fat content
        
        farmer = get_object_or_404(User, id=farmer_id)
        
        record = MilkRecord.objects.create(
            farmer=farmer,
            collector=request.user,
            quantity=quantity,
            fat_content=fat_content,
            date_collected=date_collected,
            notes=notes,
            status='Pending'
        )
        
        # Calculate estimated payment (e.g., 50 KES per liter)
        rate_per_liter = 50
        estimated_payment = float(quantity) * rate_per_liter
        
        Notification.objects.create(
            user=farmer,
            title='Milk Collected',
            message=f'{quantity}L of milk was collected by {request.user.username} on {date_collected}. Estimated payment: KES {estimated_payment:.2f}'
        )
        
        admins = User.objects.filter(profile__role='admin')
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title='New Milk Record',
                message=f'Collector {request.user.username} recorded {quantity}L from {farmer.username}.'
            )

        messages.success(
            request, 
            f'Successfully recorded {quantity}L for {farmer.username}. '
            f'Estimated payment: KES {estimated_payment:.2f}'
        )
        
        return redirect('collector_app:milk_records')
    
    # GET request - Only show farmers allocated to this collector
    allocations = CollectorAllocation.objects.filter(
        collector=request.user, 
        is_active=True
    ).select_related('farmer')
    
    farmers = [allocation.farmer for allocation in allocations]
    
    return render(request, 'collector_app/collect_milk.html', {'farmers': farmers})


@login_required
@collector_required
def milk_records(request):
    records = MilkRecord.objects.filter(collector=request.user).select_related('farmer').order_by('-date_collected')
    total = records.aggregate(total=Sum('quantity'))['total'] or 0
    return render(request, 'collector_app/milk_records.html', {
        'records': records, 'total': total
    })


@login_required
@collector_required
def view_payments(request):
    payments = Payment.objects.filter(user=request.user).order_by('-date_created')
    return render(request, 'collector_app/view_payments.html', {'payments': payments})


@login_required
@collector_required
def view_farmers(request):
    allocations = CollectorAllocation.objects.filter(
        collector=request.user, is_active=True
    ).select_related('farmer')
    
    farmers_data = []
    for alloc in allocations:
        total_milk = MilkRecord.objects.filter(
            farmer=alloc.farmer, collector=request.user
        ).aggregate(total=Sum('quantity'))['total'] or 0
        farmers_data.append({
            'farmer': alloc.farmer,
            'area': alloc.area,
            'total_milk': total_milk,
        })
    
    return render(request, 'collector_app/view_farmers.html', {'farmers_data': farmers_data})


@login_required
@collector_required
def view_profile(request):
    profile = request.user.profile  # FIXED: Changed farmer_profile to profile
    return render(request, 'collector_app/view_profile.html', {'profile': profile})


@login_required
@collector_required
def view_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.update(is_read=True)
    return render(request, 'collector_app/view_notifications.html', {'notifications': notifications})