from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
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
@collector_required
def collector_dashboard(request):
    today = timezone.now().date()
    
    # Get farmers assigned to this collector
    assigned_farmers = CollectorAllocation.objects.filter(
        collector=request.user, is_active=True
    ).values_list('farmer_id', flat=True)
    
    today_collections = MilkRecord.objects.filter(
        collector=request.user, date_collected=today
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    total_collections = MilkRecord.objects.filter(
        collector=request.user
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    my_payments = Payment.objects.filter(user=request.user, status='Approved').aggregate(
        total=Sum('amount'))['total'] or 0
    
    recent_records = MilkRecord.objects.filter(collector=request.user).order_by('-date_collected')[:5]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        'today_collections': today_collections,
        'total_collections': total_collections,
        'my_payments': my_payments,
        'farmers_count': len(assigned_farmers),
        'recent_records': recent_records,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'collector_app/dashboard.html', context)


@login_required
@collector_required
def collect_milk(request):
    # Get farmers assigned to this collector
    assigned_farmers = CollectorAllocation.objects.filter(
        collector=request.user, is_active=True
    ).select_related('farmer')
    
    if request.method == 'POST':
        farmer_id = request.POST.get('farmer')
        quantity = request.POST.get('quantity')
        fat_content = request.POST.get('fat_content')
        date_collected = request.POST.get('date_collected')
        notes = request.POST.get('notes', '')
        
        farmer = User.objects.get(id=farmer_id)
        
        MilkRecord.objects.create(
            farmer=farmer,
            collector=request.user,
            quantity=quantity,
            fat_content=fat_content,
            date_collected=date_collected or timezone.now().date(),
            notes=notes,
            status='Pending'
        )
        
        # Send notification to farmer
        Notification.objects.create(
            user=farmer,
            title='Milk Collected',
            message=f'{request.user.username} has collected {quantity}L of milk from you on {date_collected or timezone.now().date()}.'
        )
        
        # Send notification to admin (FIXED: Changed farmer_profile__role to profile__role)
        admin_users = User.objects.filter(profile__role='admin')
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New Milk Collection',
                message=f'Collector {request.user.username} collected {quantity}L from {farmer.username}.'
            )
        
        messages.success(request, f'Milk record added: {quantity}L from {farmer.username}')
        return redirect('collector_app:collect_milk')
    
    context = {
        'assigned_farmers': assigned_farmers,
    }
    return render(request, 'collector_app/collect_milk.html', context)


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