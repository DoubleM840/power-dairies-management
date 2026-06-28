from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Count
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
    
    allocated_farmers = [allocation.farmer for allocation in allocations]
    
    # Stats
    today_milk = MilkRecord.objects.filter(
        collector=request.user, date_collected=today
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    total_milk = MilkRecord.objects.filter(
        collector=request.user
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    total_farmers_visited = MilkRecord.objects.filter(
        collector=request.user
    ).values('farmer').distinct().count()
    
    pending_records = MilkRecord.objects.filter(
        collector=request.user, status='Pending'
    ).count()

    context = {
        'today_milk': today_milk,
        'total_milk': total_milk,
        'total_farmers_visited': total_farmers_visited,
        'pending_records': pending_records,
        'allocated_farmers': allocated_farmers,
        'allocations_count': allocations.count(),
    }
    return render(request, 'collector_app/dashboard.html', context)


@login_required
def collect_milk(request):
    if request.method == 'POST':
        farmer_id = request.POST.get('farmer')
        quantity = request.POST.get('quantity')
        date_collected = request.POST.get('date_collected')
        notes = request.POST.get('notes', '')
        
        # Always use standard 3.5% fat content
        fat_content = 3.5
        
        farmer = get_object_or_404(User, id=farmer_id)
        
        # Create the record
        record = MilkRecord.objects.create(
            farmer=farmer,
            collector=request.user,
            quantity=quantity,
            fat_content=fat_content,
            date_collected=date_collected,
            notes=notes,
            status='Pending'
        )
        
        # Notify farmer
        Notification.objects.create(
            user=farmer,
            title='Milk Collected',
            message=f'{quantity}L of milk was collected by {request.user.username} on {date_collected}.'
        )
        
        # Notify all Admins
        admins = User.objects.filter(profile__role='admin')
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title='New Milk Record',
                message=f'Collector {request.user.username} recorded {quantity}L from {farmer.username}.'
            )

        messages.success(request, f'Successfully recorded {quantity}L for {farmer.username}.')
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