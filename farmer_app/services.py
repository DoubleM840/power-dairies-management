from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from django.conf import settings
from django.db import models


def predict_next_month_milk(records: Sequence[object] | Iterable[object]) -> float:
    """Predict next month milk using a simple linear trend from recent records."""
    values = [float(getattr(item, 'quantity', item)) for item in list(records)]
    if len(values) < 2:
        return values[-1] if values else 0.0

    x = list(range(1, len(values) + 1))
    y = values

    # Simple linear regression using least squares
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denominator = sum((xi - mean_x) ** 2 for xi in x)

    if denominator == 0:
        return y[-1]

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    prediction = slope * (len(x) + 1) + intercept
    return round(max(prediction, 0), 2)


def calculate_milk_deduction_eligibility(user, cart_total: Decimal | int | float) -> dict:
    """Return whether a farmer can pay for feeds using their milk earnings balance."""
    from farmer_app.models import MilkRecord, Payment, Rate

    cart_total = Decimal(str(cart_total))
    active_rate = Rate.objects.filter(is_active=True).order_by('-effective_date').first()
    rate_per_liter = Decimal(str(active_rate.fat_rate)) if active_rate else Decimal('50')

    approved_liters = MilkRecord.objects.filter(
        farmer=user, status='Approved'
    ).aggregate(total=models.Sum('quantity'))['total'] or Decimal('0')
    gross_earnings = approved_liters * rate_per_liter

    committed_deductions = Payment.objects.filter(
        user=user,
        payment_type='milk_deduction',
        status__in=['Pending', 'Approved', 'Completed']
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    available_balance = gross_earnings - committed_deductions
    can_use_deduction = available_balance >= cart_total
    shortfall = max(Decimal('0'), cart_total - available_balance)

    return {
        'approved_liters': approved_liters,
        'gross_earnings': gross_earnings,
        'committed_deductions': committed_deductions,
        'available_balance': available_balance,
        'can_use_deduction': can_use_deduction,
        'shortfall': shortfall,
        'rate_per_liter': rate_per_liter,
    }


def send_sms(phone: str, message: str) -> bool:
    """Send SMS through Africa's Talking when configuration is present."""
    if not phone:
        return False

    username = getattr(settings, 'AFRICASTALKING_USERNAME', None)
    api_key = getattr(settings, 'AFRICASTALKING_API_KEY', None)
    if not username or not api_key:
        return False

    try:
        import africastalking

        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        sms.send(message, [phone])
        return True
    except Exception:
        return False
