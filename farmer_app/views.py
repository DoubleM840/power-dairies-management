from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.http import HttpResponse
from farmer_app.models import (
    UserProfile, MilkRecord, Rate, Payment, Feed, FeedOrder,
    Claim, Notification, Cow, HealthRecord, Cart, CartItem
)
from functools import wraps
from datetime import timedelta
from decimal import Decimal
import json


# FIXED: Use 'profile' not 'farmer_profile'
def farmer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        try:
            # Use 'profile' (matches your model's related_name)
            profile = request.user.profile
            if profile.role != 'farmer':
                messages.error(request, 'Access denied. Farmers only.')
                return redirect('accounts:login')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile not found.')
            return redirect('accounts:login')
        except AttributeError:
            messages.error(request, 'Access denied.')
            return redirect('accounts:login')
            
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@farmer_required
def farmer_dashboard(request):
    today = timezone.now().date()
    
    total_milk = MilkRecord.objects.filter(farmer=request.user).aggregate(
        total=Sum('quantity'))['total'] or 0
    
    this_month = MilkRecord.objects.filter(
        farmer=request.user,
        date_collected__gte=today.replace(day=1)
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    pending_payments = Payment.objects.filter(
        user=request.user, status='Pending').count()
    
    unread_notifications = Notification.objects.filter(
        user=request.user, is_read=False).count()
    
    cows_count = Cow.objects.filter(farmer=request.user).count()
    pending_orders = FeedOrder.objects.filter(
        farmer=request.user, status__in=['Pending', 'Confirmed', 'Processing']).count()
    
    # Chart data - last 7 days
    labels = []
    quantities = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        qty = MilkRecord.objects.filter(
            farmer=request.user, date_collected=date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'total_milk': total_milk,
        'this_month': this_month,
        'pending_payments': pending_payments,
        'unread_notifications': unread_notifications,
        'cows_count': cows_count,
        'pending_orders': pending_orders,
        'labels': json.dumps(labels),
        'quantities': json.dumps(quantities),
    }
    return render(request, 'farmer_app/dashboard.html', context)


# ==================== MILK RECORDS ====================
@login_required
@farmer_required
def milk_records(request):
    records = MilkRecord.objects.filter(farmer=request.user).order_by('-date_collected')
    
    today = timezone.now().date()
    labels = []
    quantities = []
    fat_contents = []
    for i in range(29, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        day_records = MilkRecord.objects.filter(farmer=request.user, date_collected=date)
        qty = day_records.aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
        fat = day_records.aggregate(avg=Avg('fat_content'))['avg'] or 0
        fat_contents.append(float(fat))
    
    context = {
        'records': records,
        'labels': json.dumps(labels),
        'quantities': json.dumps(quantities),
        'fat_contents': json.dumps(fat_contents),
    }
    return render(request, 'farmer_app/milk_records.html', context)


# ==================== FEEDS (UPDATED WITH CATEGORIES) ====================
@login_required
@farmer_required
def browse_feeds(request):
    """Browse feeds with category filtering"""
    category = request.GET.get('category', 'all')
    
    if category and category != 'all':
        feeds = Feed.objects.filter(category=category, is_active=True)
    else:
        feeds = Feed.objects.filter(is_active=True)
    
    context = {
        'feeds': feeds,
        'current_category': category,
        'total_feeds': feeds.count(),
    }
    return render(request, 'farmer_app/browse_feeds.html', context)


@login_required
@farmer_required
def order_feed(request, feed_id):
    """Add feed to cart and redirect to checkout"""
    feed = get_object_or_404(Feed, id=feed_id, is_active=True)
    
    # Get or create cart
    cart, created = Cart.objects.get_or_create(farmer=request.user)
    
    # Add to cart or update quantity
    cart_item, created = CartItem.objects.get_or_create(cart=cart, feed=feed)
    if not created:
        cart_item.quantity += 1
    else:
        cart_item.quantity = 1
    cart_item.save()
    
    messages.success(request, f'{feed.name} added to cart. Proceed to checkout.')
    return redirect('farmer_app:checkout_cart')


@login_required
@farmer_required
def my_orders(request):
    orders = FeedOrder.objects.filter(farmer=request.user).select_related('feed').order_by('-order_date')
    return render(request, 'farmer_app/my_orders.html', {'orders': orders})


@login_required
@farmer_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(farmer=request.user)
    return render(request, 'farmer_app/view_cart.html', {'cart': cart})


@login_required
@farmer_required
def add_to_cart(request, feed_id):
    feed = get_object_or_404(Feed, id=feed_id)
    cart, created = Cart.objects.get_or_create(farmer=request.user)
    
    cart_item, created = CartItem.objects.get_or_create(cart=cart, feed=feed)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{feed.name} added to cart.')
    return redirect('farmer_app:view_cart')


@login_required
@farmer_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__farmer=request.user)
    item.delete()
    messages.success(request, 'Item removed from cart.')
    return redirect('farmer_app:view_cart')


@login_required
@farmer_required
def checkout_cart(request):
    cart = get_object_or_404(Cart, farmer=request.user)
    
    if cart.items.count() == 0:
        messages.error(request, 'Your cart is empty!')
        return redirect('farmer_app:view_cart')

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        mpesa_phone = request.POST.get('mpesa_phone', '')
        use_test_mode = request.POST.get('use_test_mode') == 'true'
        total_price = cart.total_price
        
        # If using test mode or milk deduction, handle normally
        if use_test_mode and payment_method == 'mpesa':
            # Simulated test payment
            import random
            receipt = f"MPESA{random.randint(100000, 999999)}"
            
            Payment.objects.create(
                user=request.user,
                payment_type='feed_order',
                amount=total_price,
                method='M-Pesa (Test)',
                description=f'Test M-Pesa payment for feed order',
                status='Completed',
                receipt_number=receipt
            )
            
            messages.success(
                request, 
                f'Test M-Pesa Payment of KES {total_price} successful! Receipt: {receipt}. '
                f'Your order is being processed.'
            )
            
        elif payment_method == 'milk_deduction':
            # Milk Deduction Logic
            Payment.objects.create(
                user=request.user,
                payment_type='milk_deduction',
                amount=total_price,
                method='Milk Deduction',
                description=f'Feed order cost deducted from milk earnings',
                status='Pending'
            )
            
            messages.success(
                request, 
                f'KES {total_price} will be deducted from your milk earnings. '
                f'Your order is pending admin approval.'
            )
        
        # For real M-Pesa, the payment is handled via AJAX in the template
        # Create orders here
        for item in cart.items.all():
            FeedOrder.objects.create(
                farmer=request.user,
                feed=item.feed,
                quantity=item.quantity,
                total_price=item.total_price,
                status='Pending'
            )
            item.feed.stock_quantity -= item.quantity
            item.feed.save()
        
        # Clear cart
        cart.items.all().delete()
        
        return redirect('farmer_app:my_orders')
    
    return render(request, 'farmer_app/checkout_cart.html', {'cart': cart})


# ==================== PAYMENTS ====================
@login_required
@farmer_required
def farmer_earnings(request):
    """View farmer's milk earnings and deductions"""
    # Calculate total milk earnings
    milk_records = MilkRecord.objects.filter(farmer=request.user, status='Approved')
    total_milk_liters = milk_records.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Get current rate (assume KES 50 per liter for now)
    rate = 50
    gross_earnings = total_milk_liters * rate
    
    # Calculate deductions (feed orders paid via milk deduction)
    deductions = Payment.objects.filter(
        user=request.user,
        payment_type='milk_deduction',
        status__in=['Pending', 'Approved']
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    net_earnings = gross_earnings - deductions
    
    # Get payment history
    payments = Payment.objects.filter(user=request.user).order_by('-date_created')
    
    context = {
        'total_milk_liters': total_milk_liters,
        'gross_earnings': gross_earnings,
        'deductions': deductions,
        'net_earnings': net_earnings,
        'payments': payments,
        'rate_per_liter': rate,
    }
    return render(request, 'farmer_app/farmer_earnings.html', context)

@login_required
@farmer_required
def view_payments(request):
    payments = Payment.objects.filter(user=request.user).order_by('-date_created')
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        method = request.POST.get('method')
        order = get_object_or_404(FeedOrder, id=order_id, farmer=request.user)
        
        import random
        receipt_num = f"RCP-{random.randint(10000, 99999)}"
        
        Payment.objects.create(
            user=request.user,
            payment_type='feed_order',
            amount=order.total_price,
            method=method,
            description=f'Payment for {order.feed.name} x{order.quantity}',
            status='Pending',
            receipt_number=receipt_num
        )
        messages.success(request, f'Payment of KES {order.total_price} initiated via {method}.')
        return redirect('farmer_app:view_payments')
    
    return render(request, 'farmer_app/view_payments.html', {'payments': payments})


@login_required
@farmer_required
def download_receipt(request, payment_id):
    """Generate PDF receipt for a payment"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from io import BytesIO
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Header
    p.setFont("Helvetica-Bold", 24)
    p.drawString(1*inch, height - 1*inch, "DAIRY MANAGEMENT SYSTEM")
    
    p.setFont("Helvetica", 14)
    p.drawString(1*inch, height - 1.4*inch, "Payment Receipt")
    
    p.line(1*inch, height - 1.6*inch, 7*inch, height - 1.6*inch)
    
    # Receipt Details
    p.setFont("Helvetica", 12)
    y = height - 2.2*inch
    
    details = [
        ("Receipt Number:", payment.receipt_number or f"RCP-{payment.id:06d}"),
        ("Date:", payment.date_created.strftime("%B %d, %Y at %I:%M %p")),
        ("Customer:", f"{request.user.first_name} {request.user.last_name}"),
        ("Username:", request.user.username),
        ("Payment Type:", payment.get_payment_type_display()),
        ("Method:", payment.method or "N/A"),
        ("Description:", payment.description or "N/A"),
        ("Status:", payment.status),
        ("", ""),
        ("AMOUNT PAID:", f"KES {payment.amount}"),
    ]
    
    for label, value in details:
        if label == "AMOUNT PAID:":
            p.setFont("Helvetica-Bold", 14)
        p.drawString(1*inch, y, label)
        p.drawString(3.5*inch, y, str(value))
        p.setFont("Helvetica", 12)
        y -= 30
    
    # Footer
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(1*inch, 1*inch, "This is a computer-generated receipt.")
    p.drawString(1*inch, 0.7*inch, "Thank you for your business!")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number or payment.id}.pdf"'
    return response


# ==================== REPORTS ====================
@login_required
@farmer_required
def my_reports(request):
    records = MilkRecord.objects.filter(farmer=request.user)
    orders = FeedOrder.objects.filter(farmer=request.user)
    
    total_milk = records.aggregate(total=Sum('quantity'))['total'] or 0
    avg_fat = records.aggregate(avg=Avg('fat_content'))['avg'] or 0
    total_orders = orders.count()
    total_spent = orders.aggregate(total=Sum('total_price'))['total'] or 0
    
    context = {
        'records': records,
        'orders': orders,
        'total_milk': total_milk,
        'avg_fat': avg_fat,
        'total_orders': total_orders,
        'total_spent': total_spent,
    }
    return render(request, 'farmer_app/my_reports.html', context)


# ==================== LIVESTOCK ====================
@login_required
@farmer_required
def livestock_management(request):
    cows = Cow.objects.filter(farmer=request.user)
    return render(request, 'farmer_app/livestock.html', {'cows': cows})


@login_required
@farmer_required
def add_cow(request):
    if request.method == 'POST':
        cow = Cow.objects.create(
            farmer=request.user,
            tag=request.POST.get('tag'),
            breed_type=request.POST.get('breed_type'),
            name=request.POST.get('name'),
            age_months=request.POST.get('age_months', 12),
            health_status='Healthy'
        )
        
        # Notify all admins
        from django.contrib.auth.models import User
        admin_users = User.objects.filter(profile__role='admin')
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New Livestock Added',
                message=f'Farmer {request.user.username} added a new cow: {cow.name or cow.tag} ({cow.breed_type})'
            )
        
        messages.success(request, 'Cow added successfully.')
        return redirect('farmer_app:livestock_management')
    return render(request, 'farmer_app/add_cow.html')


@login_required
@farmer_required
def edit_cow(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    if request.method == 'POST':
        old_health = cow.health_status
        cow.name = request.POST.get('name')
        cow.breed_type = request.POST.get('breed_type')
        cow.age_months = request.POST.get('age_months')
        cow.health_status = request.POST.get('health_status')
        cow.save()
        
        # Notify admins if health status changed
        if old_health != cow.health_status:
            from django.contrib.auth.models import User
            admin_users = User.objects.filter(profile__role='admin')
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='Livestock Health Updated',
                    message=f'Farmer {request.user.username} updated health status of {cow.name or cow.tag} to {cow.health_status}'
                )
        
        messages.success(request, 'Cow updated successfully.')
        return redirect('farmer_app:livestock_management')
    return render(request, 'farmer_app/edit_cow.html', {'cow': cow})


@login_required
@farmer_required
def health_history(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    records = cow.health_records.all().order_by('-date')
    return render(request, 'farmer_app/health_history.html', {'cow': cow, 'records': records})


@login_required
@farmer_required
def add_health_record(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    if request.method == 'POST':
        record = HealthRecord.objects.create(
            cow=cow,
            date=request.POST.get('date'),
            description=request.POST.get('description'),
            treatment=request.POST.get('treatment'),
            vet_name=request.POST.get('vet_name')
        )
        
        # Notify admins
        from django.contrib.auth.models import User
        admin_users = User.objects.filter(profile__role='admin')
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New Health Record Added',
                message=f'Farmer {request.user.username} added a health record for {cow.name or cow.tag}: {record.description[:50]}...'
            )
        
        messages.success(request, 'Health record added.')
        return redirect('farmer_app:health_history', cow_id=cow.id)
    return render(request, 'farmer_app/add_health_record.html', {'cow': cow})

# ==================== CLAIMS ====================
@login_required
@farmer_required
def my_claims(request):
    claims = Claim.objects.filter(farmer=request.user).order_by('-date_filed')
    return render(request, 'farmer_app/my_claims.html', {'claims': claims})


@login_required
@farmer_required
def file_claim(request):
    if request.method == 'POST':
        Claim.objects.create(
            farmer=request.user,
            category=request.POST.get('category'),
            subject=request.POST.get('subject'),
            description=request.POST.get('description')
        )
        messages.success(request, 'Claim filed successfully.')
        return redirect('farmer_app:my_claims')
    return render(request, 'farmer_app/file_claim.html')


@login_required
@farmer_required
def view_claim(request, claim_id):
    claim = get_object_or_404(Claim, id=claim_id, farmer=request.user)
    return render(request, 'farmer_app/view_claim.html', {'claim': claim})


# ==================== NOTIFICATIONS ====================
@login_required
@farmer_required
def view_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.update(is_read=True)
    return render(request, 'farmer_app/notifications.html', {'notifications': notifications})


# ==================== PROFILE ====================
@login_required
@farmer_required
def view_profile(request):
    profile = request.user.profile  # FIXED: Changed from 'farmer_profile' to 'profile'
    return render(request, 'farmer_app/profile.html', {'profile': profile})