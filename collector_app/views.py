from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg
from django.http import HttpResponse
import json
from datetime import timedelta 
from farmer_app.models import (
    UserProfile, MilkRecord, Payment, Notification, CollectorAllocation, Rate
)
from farmer_app.services import send_sms
from functools import wraps


def collector_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        try:
            if request.user.profile.role != 'collector':
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
    
    # ✅ DYNAMIC COMMISSION RATE (Default: 3.0 KES/L)
    active_rate = Rate.objects.filter(is_active=True).first()
    commission_per_liter = float(active_rate.commission_rate) if active_rate else 3.0
    
    # Get allocated farmers
    allocations = CollectorAllocation.objects.filter(collector=request.user, is_active=True).select_related('farmer')
    allocated_farmers_count = allocations.count()
    
    # Stats
    today_milk = MilkRecord.objects.filter(collector=request.user, date_collected=today).aggregate(total=Sum('quantity'))['total'] or 0
    today_collections_count = MilkRecord.objects.filter(collector=request.user, date_collected=today).count()
    total_milk = MilkRecord.objects.filter(collector=request.user).aggregate(total=Sum('quantity'))['total'] or 0
    total_farmers_visited = MilkRecord.objects.filter(collector=request.user).values('farmer').distinct().count()
    pending_records = MilkRecord.objects.filter(collector=request.user, status='Pending').count()
    approved_records = MilkRecord.objects.filter(collector=request.user, status='Approved').count()
    
    # Calculate total payments for today's collections
    today_payments = Payment.objects.filter(user=request.user, date_created__date=today, status='Completed').aggregate(total=Sum('amount'))['total'] or 0
    
    # ✅ Pre-calculate commission for recent collections table
    recent_collections = MilkRecord.objects.filter(collector=request.user).select_related('farmer').order_by('-date_collected')[:10]
    recent_collections_data = []
    for record in recent_collections:
        recent_collections_data.append({
            'record': record,
            'commission': float(record.quantity) * commission_per_liter
        })
    
    # Chart data - last 7 days
    labels = []
    quantities = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        labels.append(date.strftime('%b %d'))
        qty = MilkRecord.objects.filter(collector=request.user, date_collected=date).aggregate(total=Sum('quantity'))['total'] or 0
        quantities.append(float(qty))
    
    # ✅ Calculate Total Commission
    total_commission = float(total_milk) * commission_per_liter
    
    context = {
        'today_milk': today_milk, 'today_collections_count': today_collections_count,
        'total_milk': total_milk, 'total_farmers_visited': total_farmers_visited,
        'allocated_farmers_count': allocated_farmers_count, 'pending_records': pending_records,
        'approved_records': approved_records, 'today_payments': today_payments,
        'recent_collections_data': recent_collections_data, # ✅ UPDATED
        'total_commission': total_commission,               # ✅ ADDED
        'commission_per_liter': commission_per_liter,       # ✅ ADDED
        'labels': json.dumps(labels), 'quantities': json.dumps(quantities),
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
            farmer=farmer, collector=request.user, quantity=quantity, fat_content=fat_content,
            date_collected=date_collected, notes=notes, status='Pending'
        )
        
        # ✅ DYNAMIC RATES
        active_rate = Rate.objects.filter(is_active=True).first()
        rate_per_liter = float(active_rate.fat_rate) if active_rate else 80.0
        commission_per_liter = float(active_rate.commission_rate) if active_rate else 3.0
        
        estimated_payment = float(quantity) * rate_per_liter
        estimated_commission = float(quantity) * commission_per_liter
        
        Notification.objects.create(user=farmer, title='Milk Collected', message=f'{quantity}L of milk was collected by {request.user.username} on {date_collected}. Estimated payment: KES {estimated_payment:.2f}')
        phone = farmer.profile.phone if hasattr(farmer, 'profile') and farmer.profile.phone else ''
        if phone:
            send_sms(phone, f'Power Dairies: {quantity}L milk collected today. Est. Pay: KES {estimated_payment:.2f}.')
        
        for admin in User.objects.filter(profile__role='admin'):
            Notification.objects.create(user=admin, title='New Milk Record', message=f'Collector {request.user.username} recorded {quantity}L from {farmer.username}.')

        messages.success(request, f'Successfully recorded {quantity}L for {farmer.username}. Est. Farmer Pay: KES {estimated_payment:.2f} | Your Commission: KES {estimated_commission:.2f}')
        return redirect('collector_app:milk_records')
    
    # GET request - Only show farmers allocated to this collector
    allocations = CollectorAllocation.objects.filter(collector=request.user, is_active=True).select_related('farmer')
    farmers = [allocation.farmer for allocation in allocations]
    return render(request, 'collector_app/collect_milk.html', {'farmers': farmers})


@login_required
@collector_required
def milk_records(request):
    records = MilkRecord.objects.filter(collector=request.user).select_related('farmer').order_by('-date_collected')
    total = records.aggregate(total=Sum('quantity'))['total'] or 0
    return render(request, 'collector_app/milk_records.html', {'records': records, 'total': total})


@login_required
@collector_required
def view_payments(request):
    from decimal import Decimal
    from datetime import datetime, date as _date

    today      = timezone.now().date()
    this_month = today.replace(day=1)

    # Active commission rate
    active_rate          = Rate.objects.filter(is_active=True).first()
    commission_per_liter = Decimal(str(active_rate.commission_rate)) if active_rate else Decimal('3.00')

    # ── All approved milk records for this collector ──────────────────────────
    approved_records = MilkRecord.objects.filter(
        collector=request.user, status='Approved'
    ).select_related('farmer').order_by('-date_collected')

    total_approved_liters   = approved_records.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    total_commission_earned = Decimal(str(total_approved_liters)) * commission_per_liter

    this_month_liters    = approved_records.filter(
        date_collected__gte=this_month
    ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    this_month_commission = Decimal(str(this_month_liters)) * commission_per_liter

    pending_liters = MilkRecord.objects.filter(
        collector=request.user, status='Pending'
    ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    pending_commission = Decimal(str(pending_liters)) * commission_per_liter

    # ── Filters ───────────────────────────────────────────────────────────────
    status_filter    = request.GET.get('status', '').strip()
    date_range       = request.GET.get('range', '').strip()   # all|week|month|last_month|custom
    date_from_str    = request.GET.get('date_from', '').strip()
    date_to_str      = request.GET.get('date_to', '').strip()

    payments_qs = Payment.objects.filter(user=request.user).order_by('date_created')

    # Status filter
    if status_filter:
        payments_qs = payments_qs.filter(status__iexact=status_filter)

    # Date range filter
    date_from = date_to = None
    if date_range == 'week':
        date_from = today - timedelta(days=7)
    elif date_range == 'month':
        date_from = this_month
    elif date_range == 'last_month':
        first_of_last = (this_month - timedelta(days=1)).replace(day=1)
        date_from = first_of_last
        date_to   = this_month
    elif date_range == 'custom':
        try:
            date_from = _date.fromisoformat(date_from_str) if date_from_str else None
        except ValueError:
            date_from = None
        try:
            date_to = _date.fromisoformat(date_to_str) if date_to_str else None
        except ValueError:
            date_to = None

    if date_from:
        payments_qs = payments_qs.filter(date_created__date__gte=date_from)
    if date_to:
        payments_qs = payments_qs.filter(date_created__date__lt=date_to)

    # Evaluate once — needed for running balance and footer
    payments_list = list(payments_qs)

    # ── Running balance (cumulative, oldest→newest) ───────────────────────────
    running = Decimal('0')
    payments_with_balance = []
    for pmt in payments_list:
        if pmt.status in ('Completed', 'Approved'):
            running += pmt.amount
        payments_with_balance.append({
            'payment': pmt,
            'running_balance': running,
        })
    # Reverse so newest is at top in the template
    payments_with_balance.reverse()

    # ── Footer totals (respecting active filters) ─────────────────────────────
    filtered_total   = sum(p['payment'].amount for p in payments_with_balance)
    filtered_completed = sum(
        p['payment'].amount for p in payments_with_balance
        if p['payment'].status in ('Completed', 'Approved')
    )
    filtered_count   = len(payments_with_balance)

    total_paid = Payment.objects.filter(
        user=request.user, status__in=['Completed', 'Approved']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # ── Commission breakdown per approved record ──────────────────────────────
    records_with_commission = [
        {
            'record':     r,
            'commission': Decimal(str(r.quantity)) * commission_per_liter,
        }
        for r in approved_records
    ]

    # ── Monthly earnings chart — last 6 months ────────────────────────────────
    chart_labels     = []
    chart_commission = []
    chart_liters     = []
    for i in range(5, -1, -1):
        month_offset = today.month - i
        year_offset  = today.year
        while month_offset <= 0:
            month_offset += 12
            year_offset  -= 1
        month_start = today.replace(year=year_offset, month=month_offset, day=1)
        month_end   = (
            month_start.replace(month=month_start.month % 12 + 1, day=1)
            if month_start.month < 12
            else month_start.replace(year=month_start.year + 1, month=1, day=1)
        )
        liters = MilkRecord.objects.filter(
            collector=request.user, status='Approved',
            date_collected__gte=month_start,
            date_collected__lt=month_end,
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        chart_labels.append(month_start.strftime('%b %Y'))
        chart_liters.append(float(liters))
        chart_commission.append(float(Decimal(str(liters)) * commission_per_liter))

    context = {
        'payments_with_balance':  payments_with_balance,
        'status_filter':          status_filter,
        'date_range':             date_range,
        'date_from':              date_from_str,
        'date_to':                date_to_str,
        'commission_per_liter':   commission_per_liter,
        # Summary stats
        'total_approved_liters':  total_approved_liters,
        'total_commission_earned':total_commission_earned,
        'this_month_commission':  this_month_commission,
        'this_month_liters':      this_month_liters,
        'pending_commission':     pending_commission,
        'pending_liters':         pending_liters,
        'total_paid':             total_paid,
        # Footer totals
        'filtered_total':         filtered_total,
        'filtered_completed':     filtered_completed,
        'filtered_count':         filtered_count,
        # Breakdown table
        'records_with_commission':records_with_commission,
        # Chart
        'chart_labels':           json.dumps(chart_labels),
        'chart_commission':       json.dumps(chart_commission),
        'chart_liters':           json.dumps(chart_liters),
    }
    return render(request, 'collector_app/view_payments.html', context)


@login_required
@collector_required
def download_payment_receipt(request, payment_id):
    """PDF receipt for a single payment record."""
    from decimal import Decimal
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rl_canvas

    payment = get_object_or_404(Payment, id=payment_id, user=request.user)

    buf = BytesIO()
    p   = rl_canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Header bar
    p.setFillColor(colors.HexColor('#27ae60'))
    p.rect(0.5*inch, H - 0.95*inch, W - inch, 0.75*inch, fill=True, stroke=False)
    p.setFillColor(colors.white)
    p.setFont('Helvetica-Bold', 20)
    p.drawString(0.75*inch, H - 0.62*inch, 'Power Dairies — Payment Receipt')

    # Divider
    p.setStrokeColor(colors.HexColor('#27ae60'))
    p.setLineWidth(1.5)
    p.line(0.5*inch, H - 1.1*inch, W - 0.5*inch, H - 1.1*inch)

    # Details
    p.setFillColor(colors.HexColor('#2c3e50'))
    p.setFont('Helvetica', 12)
    details = [
        ('Receipt Number',  payment.receipt_number or f'RCP-{payment.id:06d}'),
        ('Date',            payment.date_created.strftime('%B %d, %Y at %I:%M %p')),
        ('Collector',       request.user.get_full_name() or request.user.username),
        ('Username',        request.user.username),
        ('Payment Type',    payment.get_payment_type_display()),
        ('Method',          payment.method or 'N/A'),
        ('Description',     (payment.description or 'N/A')[:60]),
        ('Status',          payment.status),
    ]
    y = H - 1.5*inch
    for label, value in details:
        p.setFont('Helvetica-Bold', 11)
        p.drawString(0.75*inch, y, f'{label}:')
        p.setFont('Helvetica', 11)
        p.drawString(3.0*inch, y, str(value))
        y -= 0.3*inch

    # Amount box
    y -= 0.15*inch
    p.setFillColor(colors.HexColor('#f8f9fa'))
    p.roundRect(0.5*inch, y - 0.1*inch, W - inch, 0.55*inch, 6, fill=True, stroke=False)
    p.setFont('Helvetica-Bold', 16)
    p.setFillColor(colors.HexColor('#27ae60'))
    p.drawString(0.75*inch, y + 0.2*inch, 'AMOUNT PAID:')
    p.drawString(3.5*inch,  y + 0.2*inch, f'KES {payment.amount:,.2f}')

    p.setFont('Helvetica-Oblique', 9)
    p.setFillColor(colors.grey)
    p.drawString(0.5*inch, 0.5*inch,
                 'Power Dairies — Computer-generated receipt. Not valid as tax invoice.')
    p.showPage()
    p.save()
    buf.seek(0)

    receipt_ref = payment.receipt_number or payment.id
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="receipt_{receipt_ref}_{request.user.username}.pdf"'
    )
    return response


@login_required
@collector_required
def download_commission_slip(request, month=None):
    """Generate a PDF monthly commission slip for the collector."""
    from decimal import Decimal
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rl_canvas

    if month is None:
        month = timezone.now().date().strftime('%Y-%m')

    year, month_number = map(int, month.split('-'))
    from datetime import date as _date
    start_date = _date(year, month_number, 1)
    if month_number == 12:
        end_date = _date(year + 1, 1, 1)
    else:
        end_date = _date(year, month_number + 1, 1)

    active_rate          = Rate.objects.filter(is_active=True).first()
    commission_per_liter = Decimal(str(active_rate.commission_rate)) if active_rate else Decimal('3.00')

    records = MilkRecord.objects.filter(
        collector=request.user,
        status='Approved',
        date_collected__gte=start_date,
        date_collected__lt=end_date,
    ).select_related('farmer').order_by('date_collected')

    total_liters     = records.aggregate(t=Sum('quantity'))['t'] or Decimal('0')
    total_commission = Decimal(str(total_liters)) * commission_per_liter
    total_collections = records.count()
    unique_farmers   = records.values('farmer').distinct().count()

    # ── Build PDF ─────────────────────────────────────────────────────────────
    buf = BytesIO()
    p   = rl_canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Header bar
    p.setFillColor(colors.HexColor('#27ae60'))
    p.rect(0.5*inch, H - 0.95*inch, W - inch, 0.75*inch, fill=True, stroke=False)
    p.setFillColor(colors.white)
    p.setFont('Helvetica-Bold', 18)
    p.drawString(0.75*inch, H - 0.62*inch, 'Power Dairies — Collector Commission Slip')

    # Sub-header
    p.setFillColor(colors.HexColor('#2c3e50'))
    p.setFont('Helvetica', 11)
    p.drawString(0.75*inch, H - 1.2*inch,
                 f'Collector: {request.user.get_full_name() or request.user.username}')
    p.drawString(0.75*inch, H - 1.4*inch,
                 f'Period: {start_date.strftime("%B %Y")}')
    p.drawString(0.75*inch, H - 1.6*inch,
                 f'Commission Rate: KES {commission_per_liter}/L')

    # Summary box
    box_y = H - 2.6*inch
    p.setFillColor(colors.HexColor('#f8f9fa'))
    p.roundRect(0.5*inch, box_y, W - inch, 0.8*inch, 6, fill=True, stroke=False)
    p.setFont('Helvetica-Bold', 12)
    p.setFillColor(colors.HexColor('#27ae60'))
    col = [0.75*inch, 2.8*inch, 4.85*inch]
    p.drawString(col[0], box_y + 0.52*inch, 'Total Litres Collected')
    p.drawString(col[1], box_y + 0.52*inch, 'Collections')
    p.drawString(col[2], box_y + 0.52*inch, 'Total Commission')
    p.setFont('Helvetica-Bold', 14)
    p.setFillColor(colors.HexColor('#2c3e50'))
    p.drawString(col[0], box_y + 0.2*inch,  f'{total_liters:.2f} L')
    p.drawString(col[1], box_y + 0.2*inch,  str(total_collections))
    p.setFillColor(colors.HexColor('#27ae60'))
    p.drawString(col[2], box_y + 0.2*inch,  f'KES {total_commission:.2f}')

    # Table header
    p.setFillColor(colors.HexColor('#27ae60'))
    p.setFont('Helvetica-Bold', 10)
    table_top = box_y - 0.4*inch
    headers = ['Date', 'Farmer', 'Litres (L)', 'Commission (KES)', 'Status']
    col_x   = [0.5*inch, 1.5*inch, 3.5*inch, 4.6*inch, 6.1*inch]
    for hdr, cx in zip(headers, col_x):
        p.drawString(cx, table_top, hdr)

    p.setStrokeColor(colors.HexColor('#27ae60'))
    p.line(0.5*inch, table_top - 4, W - 0.5*inch, table_top - 4)

    # Table rows
    p.setFont('Helvetica', 9)
    row_y = table_top - 0.25*inch
    for idx, record in enumerate(records):
        if row_y < 1.2*inch:        # new page
            p.showPage()
            row_y = H - 0.75*inch
            p.setFont('Helvetica', 9)

        bg = colors.HexColor('#f8f9fa') if idx % 2 == 0 else colors.white
        p.setFillColor(bg)
        p.rect(0.5*inch, row_y - 4, W - inch, 0.22*inch, fill=True, stroke=False)

        commission = Decimal(str(record.quantity)) * commission_per_liter
        p.setFillColor(colors.HexColor('#2c3e50'))
        p.drawString(col_x[0], row_y, record.date_collected.strftime('%d %b %Y'))
        p.drawString(col_x[1], row_y,
                     (record.farmer.get_full_name() or record.farmer.username)[:22])
        p.drawString(col_x[2], row_y, f'{record.quantity:.2f}')
        p.setFillColor(colors.HexColor('#27ae60'))
        p.drawString(col_x[3], row_y, f'{commission:.2f}')
        p.setFillColor(colors.HexColor('#2c3e50'))
        p.drawString(col_x[4], row_y, record.status)
        row_y -= 0.25*inch

    # Footer
    p.setFont('Helvetica-Oblique', 9)
    p.setFillColor(colors.grey)
    p.drawString(0.5*inch, 0.5*inch, 'Power Dairies — Computer-generated commission slip')

    p.showPage()
    p.save()
    buf.seek(0)

    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="commission_slip_{month}_{request.user.username}.pdf"'
    )
    return response


@login_required
@collector_required
def view_farmers(request):
    allocations = CollectorAllocation.objects.filter(collector=request.user, is_active=True).select_related('farmer')
    farmers_data = []
    for alloc in allocations:
        total_milk = MilkRecord.objects.filter(farmer=alloc.farmer, collector=request.user).aggregate(total=Sum('quantity'))['total'] or 0
        farmers_data.append({'farmer': alloc.farmer, 'area': alloc.area, 'total_milk': total_milk})
    return render(request, 'collector_app/view_farmers.html', {'farmers_data': farmers_data})


@login_required
@collector_required
def view_profile(request):
    return render(request, 'collector_app/view_profile.html', {'profile': request.user.profile})


@login_required
@collector_required
def view_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.update(is_read=True)
    return render(request, 'collector_app/view_notifications.html', {'notifications': notifications})