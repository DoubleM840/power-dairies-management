from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.http import HttpResponse
from farmer_app.models import (
    UserProfile, MilkRecord, Rate, Payment, Feed, FeedOrder,
    Claim, Notification, Cow, HealthRecord, Cart, CartItem, BreedingRecord
)
from farmer_app.services import calculate_milk_deduction_eligibility, predict_next_month_milk, send_sms
from functools import wraps
from datetime import datetime, timedelta
from decimal import Decimal
import json


def farmer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        try:
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
    
    # Milk Statistics
    total_milk = MilkRecord.objects.filter(farmer=request.user).aggregate(total=Sum('quantity'))['total'] or 0
    this_month = MilkRecord.objects.filter(farmer=request.user, date_collected__gte=today.replace(day=1)).aggregate(total=Sum('quantity'))['total'] or 0
    today_milk = MilkRecord.objects.filter(farmer=request.user, date_collected=today).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Financial Overview
    approved_milk = MilkRecord.objects.filter(farmer=request.user, status='Approved')
    total_liters = approved_milk.aggregate(total=Sum('quantity'))['total'] or Decimal('0.00')
    
    # ✅ DYNAMIC RATE: Fetch active rate as Decimal (Default: 80.00 KES/L)
    active_rate = Rate.objects.filter(is_active=True).first()
    rate_per_liter = Decimal(str(active_rate.fat_rate)) if active_rate else Decimal('80.00')
    
    # Calculate earnings using Decimals
    gross_earnings = Decimal(str(total_liters)) * rate_per_liter
    
    # Get deductions (Sum returns a Decimal)
    deductions = Payment.objects.filter(
        user=request.user, payment_type='milk_deduction', status__in=['Pending', 'Completed']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # ✅ Now both are Decimals, so subtraction works perfectly
    net_earnings = gross_earnings - deductions
    
    pending_payments = Payment.objects.filter(user=request.user, status='Pending').count()
    
    # Orders
    pending_orders = FeedOrder.objects.filter(farmer=request.user, status__in=['Pending', 'Confirmed', 'Processing']).count()
    completed_orders = FeedOrder.objects.filter(farmer=request.user, status='Delivered').count()
    
    # Livestock
    cows_count = Cow.objects.filter(farmer=request.user).count()
    healthy_cows = Cow.objects.filter(farmer=request.user, health_status='Healthy').count()
    
    # Notifications
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Recent milk records
    recent_records = MilkRecord.objects.filter(farmer=request.user).order_by('-date_collected')[:5]
    recent_monthly_records = list(MilkRecord.objects.filter(farmer=request.user, status='Approved').order_by('-date_collected')[:6])
    forecast_next_month = predict_next_month_milk(recent_monthly_records)
    
    # Recent orders
    recent_orders = FeedOrder.objects.filter(farmer=request.user).select_related('feed').order_by('-order_date')[:5]
    
    # Chart data - last 7 days
    labels = []
    quantities = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        qty = MilkRecord.objects.filter(farmer=request.user, date_collected=date).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    context = {
        'total_milk': total_milk, 'this_month': this_month, 'today_milk': today_milk,
        'gross_earnings': gross_earnings, 'deductions': deductions, 'net_earnings': net_earnings,
        'pending_payments': pending_payments, 'unread_notifications': unread_notifications,
        'cows_count': cows_count, 'healthy_cows': healthy_cows, 'pending_orders': pending_orders,
        'completed_orders': completed_orders, 'recent_records': recent_records, 'recent_orders': recent_orders,
        'rate_per_liter': rate_per_liter, 
        'labels': json.dumps(labels), 'quantities': json.dumps(quantities), 'forecast_next_month': forecast_next_month,
    }
    return render(request, 'farmer_app/dashboard.html', context)

@login_required
@farmer_required
def milk_records(request):
    records = MilkRecord.objects.filter(farmer=request.user).order_by('-date_collected')
    today = timezone.now().date()
    labels, quantities, fat_contents = [], [], []
    for i in range(29, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        day_records = MilkRecord.objects.filter(farmer=request.user, date_collected=date)
        quantities.append(float(day_records.aggregate(total=Sum('quantity'))['total'] or 0))
        fat_contents.append(float(day_records.aggregate(avg=Avg('fat_content'))['avg'] or 0))
    
    recent_records = list(records.filter(status='Approved')[:6])
    forecast_next_month = predict_next_month_milk(recent_records)

    context = {
        'records': records, 'labels': json.dumps(labels), 'quantities': json.dumps(quantities),
        'fat_contents': json.dumps(fat_contents), 'forecast_next_month': forecast_next_month,
    }
    return render(request, 'farmer_app/milk_records.html', context)


@login_required
@farmer_required
def browse_feeds(request):
    category = request.GET.get('category', 'all')
    feeds = Feed.objects.filter(category=category, is_active=True) if category != 'all' else Feed.objects.filter(is_active=True)
    return render(request, 'farmer_app/browse_feeds.html', {'feeds': feeds, 'current_category': category, 'total_feeds': feeds.count()})


@login_required
@farmer_required
def order_feed(request, feed_id):
    feed = get_object_or_404(Feed, id=feed_id, is_active=True)
    quantity = int(request.GET.get('quantity', request.POST.get('quantity', 1)))
    cart, created = Cart.objects.get_or_create(farmer=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, feed=feed)
    cart_item.quantity += quantity if not created else quantity
    cart_item.save()
    messages.success(request, f'{quantity} {feed.unit} of {feed.name} added to cart.')
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
    quantity = int(request.GET.get('quantity', request.POST.get('quantity', 1)))
    cart, created = Cart.objects.get_or_create(farmer=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, feed=feed)
    cart_item.quantity += quantity if not created else quantity
    cart_item.save()
    messages.success(request, f'{quantity} {feed.unit} of {feed.name} added to cart.')
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

    cart_total = Decimal(str(cart.total_price))
    eligibility = calculate_milk_deduction_eligibility(request.user, cart_total)

    if request.method == 'POST':
        # Only milk_deduction comes through this view as a regular POST.
        # M-Pesa STK Push is handled entirely by mpesa/views.py via AJAX.
        payment_method = request.POST.get('payment_method')

        if payment_method != 'milk_deduction':
            messages.error(request, 'Invalid payment method.')
            return redirect('farmer_app:checkout_cart')

        if not eligibility['can_use_deduction']:
            messages.error(
                request,
                f'Insufficient milk earnings. Shortfall: KES {eligibility["shortfall"]:,.2f}. '
                'Please use M-Pesa instead.'
            )
            return redirect('farmer_app:checkout_cart')

        # Record the deduction payment
        Payment.objects.create(
            user=request.user,
            payment_type='milk_deduction',
            amount=cart_total,
            method='Milk Deduction',
            description=(
                f'Feed order deducted from milk earnings. '
                f'Balance before deduction: KES {eligibility["available_balance"]:,.2f}'
            ),
            status='Pending',
        )

        # Create feed orders and deduct stock
        for item in cart.items.select_related('feed').all():
            FeedOrder.objects.create(
                farmer=request.user,
                feed=item.feed,
                quantity=item.quantity,
                total_price=item.total_price,
                status='Pending',
                payment_method='Milk Deduction',
            )
            item.feed.stock_quantity -= item.quantity
            item.feed.save()

        cart.items.all().delete()
        messages.success(
            request,
            f'Order placed. KES {cart_total} will be deducted from your milk earnings.'
        )
        return redirect('farmer_app:my_orders')

    context = {
        'cart': cart,
        'available_balance': eligibility['available_balance'],
        'can_use_deduction': eligibility['can_use_deduction'],
        'shortfall': eligibility['shortfall'],
        'cart_total': cart_total,
        'rate_per_liter': eligibility['rate_per_liter'],
        'gross_earnings': eligibility['gross_earnings'],
        'committed_deductions': eligibility['committed_deductions'],
        'approved_liters': eligibility['approved_liters'],
        'eligibility': eligibility,
    }
    return render(request, 'farmer_app/checkout_cart.html', context)


@login_required
@farmer_required
def farmer_earnings(request):
    eligibility = calculate_milk_deduction_eligibility(request.user, Decimal('0'))
    payments = Payment.objects.filter(user=request.user).order_by('-date_created')
    context = {
        'total_milk_liters': eligibility['approved_liters'], 'gross_earnings': eligibility['gross_earnings'],
        'deductions': eligibility['committed_deductions'], 'net_earnings': eligibility['gross_earnings'] - eligibility['committed_deductions'],
        'available_balance': eligibility['available_balance'], 'payments': payments, 'rate_per_liter': eligibility['rate_per_liter'],
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
        Payment.objects.create(user=request.user, payment_type='feed_order', amount=order.total_price, method=method, description=f'Payment for {order.feed.name} x{order.quantity}', status='Pending', receipt_number=receipt_num)
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
    
    p.setFont("Helvetica-Bold", 24)
    p.drawString(1*inch, height - 1*inch, "DAIRY MANAGEMENT SYSTEM")
    p.setFont("Helvetica", 14)
    p.drawString(1*inch, height - 1.4*inch, "Payment Receipt")
    p.line(1*inch, height - 1.6*inch, 7*inch, height - 1.6*inch)
    
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
        if label == "AMOUNT PAID:": p.setFont("Helvetica-Bold", 14)
        p.drawString(1*inch, y, label)
        p.drawString(3.5*inch, y, str(value))
        p.setFont("Helvetica", 12)
        y -= 30
    
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(1*inch, 1*inch, "This is a computer-generated receipt.")
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number or payment.id}.pdf"'
    return response


@login_required
@farmer_required
def my_reports(request):
    records = MilkRecord.objects.filter(farmer=request.user)
    orders = FeedOrder.objects.filter(farmer=request.user)
    context = {
        'records': records, 'orders': orders,
        'total_milk': records.aggregate(total=Sum('quantity'))['total'] or 0,
        'avg_fat': records.aggregate(avg=Avg('fat_content'))['avg'] or 0,
        'total_orders': orders.count(),
        'total_spent': orders.aggregate(total=Sum('total_price'))['total'] or 0,
    }
    return render(request, 'farmer_app/my_reports.html', context)


@login_required
@farmer_required
def download_milk_slip(request, month=None):
    if month is None: month = timezone.now().date().strftime('%Y-%m')
    year, month_number = map(int, month.split('-'))
    start_date = datetime(year, month_number, 1).date()
    next_month = datetime(year + 1, 1, 1).date() if month_number == 12 else datetime(year, month_number + 1, 1).date()

    records = MilkRecord.objects.filter(farmer=request.user, date_collected__gte=start_date, date_collected__lt=next_month, status='Approved').order_by('date_collected')
    total_liters = records.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    avg_fat = records.aggregate(avg=Avg('fat_content'))['avg'] or Decimal('0')
    avg_snf = (avg_fat * Decimal('0.35')) + Decimal('8.5') if records else Decimal('0')

    # ✅ DYNAMIC RATE for PDF
    active_rate = Rate.objects.filter(is_active=True).first()
    rate_per_liter = Decimal(str(active_rate.fat_rate)) if active_rate else Decimal('80.00')
    
    gross_earnings = total_liters * rate_per_liter
    deductions = Payment.objects.filter(user=request.user, payment_type='milk_deduction', status__in=['Pending', 'Approved', 'Completed']).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    net_earnings = gross_earnings - deductions

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from io import BytesIO

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFillColorRGB(0.11, 0.19, 0.38)
    p.rect(0.5 * inch, height - 0.9 * inch, width - 1 * inch, 0.7 * inch, fill=True, stroke=False)
    p.setFillColorRGB(1, 1, 1)
    p.setFont('Helvetica-Bold', 20)
    p.drawString(0.8 * inch, height - 0.6 * inch, 'Power Dairies - Milk Slip')

    p.setFillColorRGB(0.15, 0.15, 0.15)
    p.setFont('Helvetica', 11)
    p.drawString(0.8 * inch, height - 1.1 * inch, f'Farmer: {request.user.get_full_name() or request.user.username}')
    p.drawString(0.8 * inch, height - 1.35 * inch, f'Period: {start_date.strftime("%B %Y")}')

    p.setFont('Helvetica-Bold', 12)
    p.drawString(0.8 * inch, height - 1.8 * inch, 'Payment Summary')
    p.setFont('Helvetica', 11)
    y = height - 2.2 * inch
    for label, value in [
        ('Approved Milk:', f'{total_liters:.2f} L'), ('Average Fat %:', f'{avg_fat:.2f}%'),
        ('Estimated SNF:', f'{avg_snf:.2f}%'), ('Gross Earnings:', f'KES {gross_earnings:.2f}'),
        ('Deductions:', f'KES {deductions:.2f}'), ('Net Pay:', f'KES {net_earnings:.2f}'),
    ]:
        p.drawString(0.8 * inch, y, label)
        p.drawString(4.4 * inch, y, str(value))
        y -= 0.25 * inch

    p.setFont('Helvetica-Oblique', 10)
    p.drawString(0.8 * inch, 0.8 * inch, 'This is a computer-generated milk slip from Power Dairies.')
    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="milk_slip_{month}.pdf"'
    return response


@login_required
@farmer_required
def breeding_management(request):
    cows = Cow.objects.filter(farmer=request.user)
    records = BreedingRecord.objects.filter(farmer=request.user).select_related('cow').order_by('-insemination_date')
    return render(request, 'farmer_app/breeding_management.html', {'cows': cows, 'records': records})


@login_required
@farmer_required
def add_breeding_record(request):
    if request.method == 'POST':
        cow = get_object_or_404(Cow, id=request.POST.get('cow'), farmer=request.user)
        BreedingRecord.objects.create(cow=cow, farmer=request.user, last_heat_date=request.POST.get('last_heat_date') or None, insemination_date=request.POST.get('insemination_date'), insemination_type=request.POST.get('insemination_type', 'AI'), bull_or_sire=request.POST.get('bull_or_sire') or '', status='Inseminated')
        messages.success(request, 'Breeding record created successfully.')
        return redirect('farmer_app:breeding_management')
    return render(request, 'farmer_app/add_breeding_record.html', {'cows': Cow.objects.filter(farmer=request.user)})


@login_required
@farmer_required
def send_calving_alerts(request):
    today = timezone.now().date()
    upcoming = BreedingRecord.objects.filter(farmer=request.user, expected_calving_date__gte=today, expected_calving_date__lte=today + timedelta(days=14), alert_sent=False)
    for record in upcoming:
        message = f"Power Dairies: {record.cow.name or 'Your cow'} is due to calve in {record.days_to_calving} days."
        sent = send_sms(request.user.profile.phone if hasattr(request.user, 'profile') else '', message)
        record.alert_sent = True
        record.save(update_fields=['alert_sent'])
    messages.success(request, 'Calving reminders were checked.')
    return redirect('farmer_app:breeding_management')


@login_required
@farmer_required
def livestock_management(request):
    return render(request, 'farmer_app/livestock.html', {'cows': Cow.objects.filter(farmer=request.user)})


@login_required
@farmer_required
def add_cow(request):
    if request.method == 'POST':
        cow = Cow.objects.create(farmer=request.user, tag=request.POST.get('tag'), breed_type=request.POST.get('breed_type'), name=request.POST.get('name'), age_months=request.POST.get('age_months', 12), health_status='Healthy')
        from django.contrib.auth.models import User
        for admin in User.objects.filter(profile__role='admin'):
            Notification.objects.create(user=admin, title='New Livestock Added', message=f'Farmer {request.user.username} added a new cow: {cow.name or cow.tag} ({cow.breed_type})')
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
        if old_health != cow.health_status:
            from django.contrib.auth.models import User
            for admin in User.objects.filter(profile__role='admin'):
                Notification.objects.create(user=admin, title='Livestock Health Updated', message=f'Farmer {request.user.username} updated health status of {cow.name or cow.tag} to {cow.health_status}')
        messages.success(request, 'Cow updated successfully.')
        return redirect('farmer_app:livestock_management')
    return render(request, 'farmer_app/edit_cow.html', {'cow': cow})


@login_required
@farmer_required
def health_history(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    return render(request, 'farmer_app/health_history.html', {'cow': cow, 'records': cow.health_records.all().order_by('-date')})


@login_required
@farmer_required
def add_health_record(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farmer=request.user)
    if request.method == 'POST':
        record = HealthRecord.objects.create(cow=cow, date=request.POST.get('date'), description=request.POST.get('description'), treatment=request.POST.get('treatment'), vet_name=request.POST.get('vet_name'))
        from django.contrib.auth.models import User
        for admin in User.objects.filter(profile__role='admin'):
            Notification.objects.create(user=admin, title='New Health Record Added', message=f'Farmer {request.user.username} added a health record for {cow.name or cow.tag}: {record.description[:50]}...')
        messages.success(request, 'Health record added.')
        return redirect('farmer_app:health_history', cow_id=cow.id)
    return render(request, 'farmer_app/add_health_record.html', {'cow': cow})


@login_required
@farmer_required
def my_claims(request):
    return render(request, 'farmer_app/my_claims.html', {'claims': Claim.objects.filter(farmer=request.user).order_by('-date_filed')})


@login_required
@farmer_required
def file_claim(request):
    if request.method == 'POST':
        Claim.objects.create(farmer=request.user, category=request.POST.get('category'), subject=request.POST.get('subject'), description=request.POST.get('description'))
        messages.success(request, 'Claim filed successfully.')
        return redirect('farmer_app:my_claims')
    return render(request, 'farmer_app/file_claim.html')


@login_required
@farmer_required
def view_claim(request, claim_id):
    return render(request, 'farmer_app/view_claim.html', {'claim': get_object_or_404(Claim, id=claim_id, farmer=request.user)})


@login_required
@farmer_required
def view_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.update(is_read=True)
    return render(request, 'farmer_app/notifications.html', {'notifications': notifications})


@login_required
@farmer_required
def view_profile(request):
    return render(request, 'farmer_app/profile.html', {'profile': request.user.profile})