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


def farmer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')  # FIXED: Added 'accounts:' namespace
        try:
            if request.user.profile.role != 'farmer':  # FIXED: Changed farmer_profile to profile
                messages.error(request, 'Access denied. Farmers only.')
                return redirect('accounts:login')
        except UserProfile.DoesNotExist:
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
    
    # Chart data
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


# ==================== FEEDS ====================
@login_required
@farmer_required
def view_feeds(request):
    feeds = Feed.objects.filter(is_active=True)
    return render(request, 'farmer_app/view_feeds.html', {'feeds': feeds})


@login_required
@farmer_required
def order_feed(request, feed_id):
    feed = get_object_or_404(Feed, id=feed_id)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        total_price = feed.price * quantity
        
        FeedOrder.objects.create(
            farmer=request.user,
            feed=feed,
            quantity=quantity,
            total_price=total_price,
            status='Pending'
        )
        messages.success(request, f'Order placed for {quantity} {feed.unit} of {feed.name}.')
        return redirect('farmer_app:my_orders')
    return render(request, 'farmer_app/order_feed.html', {'feed': feed})


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
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        for item in cart.items.all():
            # Create feed order
            FeedOrder.objects.create(
                farmer=request.user,
                feed=item.feed,
                quantity=item.quantity,
                total_price=item.total_price,
                status='Pending'
            )
            # Reduce stock
            item.feed.stock_quantity -= item.quantity
            item.feed.save()
        
        # Clear cart
        cart.items.all().delete()
        messages.success(request, 'Order placed successfully! Choose payment method.')
        return redirect('farmer_app:my_orders')
    
    return render(request, 'farmer_app/checkout_cart.html', {'cart': cart})


# ==================== PAYMENTS ====================
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
    
    # Details
    p.setFont("Helvetica", 12)
    y = height - 2.2*inch
    
    details = [
        (f"Receipt Number:", payment.receipt_number or "N/A"),
        (f"Date:", payment.date_created.strftime("%B %d, %Y")),
        (f"Customer:", f"{request.user.first_name} {request.user.last_name}"),
        (f"Username:", request.user.username),
        (f"Payment Type:", payment.get_payment_type_display()),
        (f"Method:", payment.method or "N/A"),
        (f"Description:", payment.description or "N/A"),
        (f"Status:", payment.status),
        ("", ""),
        (f"AMOUNT PAID:", f"KES {payment.amount}"),
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
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number}.pdf"'
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
        Cow.objects.create(
            farmer=request.user,
            tag=request.POST.get('tag'),
            breed_type=request.POST.get('breed_type'),
            name=request.POST.get('name'),
            age_months=request.POST.get('age_months', 12),
            health_status='Healthy'
        )
        messages.success(request, 'Cow added successfully.')
        return redirect('farmer_app:livestock_management')
    return render(request, 'farmer_app/add_cow.html')


@login_required
@farmer_required
def edit_cow(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    if request.method == 'POST':
        cow.name = request.POST.get('name')
        cow.breed_type = request.POST.get('breed_type')
        cow.age_months = request.POST.get('age_months')
        cow.health_status = request.POST.get('health_status')
        cow.save()
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
        HealthRecord.objects.create(
            cow=cow,
            date=request.POST.get('date'),
            description=request.POST.get('description'),
            treatment=request.POST.get('treatment'),
            vet_name=request.POST.get('vet_name')
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
    profile = request.user.profile  # FIXED: Changed farmer_profile to profile
    return render(request, 'farmer_app/profile.html', {'profile': profile})