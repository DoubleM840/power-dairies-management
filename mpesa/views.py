import json
import time
import logging

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .services import MpesaService
from .models import MpesaTransaction
from farmer_app.models import Payment, FeedOrder, Cart

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared fulfilment helper
# Called by BOTH the Safaricom callback AND the status-check polling view.
# Idempotent: safe to call multiple times for the same transaction.
# ─────────────────────────────────────────────────────────────────────────────
def _fulfil_completed_transaction(transaction, receipt_number=None):
    """
    Given a COMPLETED MpesaTransaction:
      1. Create a Payment record (if one doesn't already exist for this receipt).
      2. Convert the user's cart items into FeedOrder records.
      3. Deduct stock for each item.
      4. Clear the cart.

    receipt_number is optional — the callback supplies it; the query path may not.
    """
    user = transaction.user

    # ── 1. Payment record ────────────────────────────────────────────────────
    receipt = receipt_number or transaction.mpesa_receipt_number
    # Guard against duplicates keyed on receipt number or checkout_request_id
    payment_exists = (
        (receipt and Payment.objects.filter(receipt_number=receipt).exists())
        or Payment.objects.filter(
            user=user,
            description__icontains=transaction.checkout_request_id,
        ).exists()
    )
    if not payment_exists:
        Payment.objects.create(
            user=user,
            payment_type='feed_order',
            amount=transaction.amount,
            method='M-Pesa',
            description=(
                f'M-Pesa STK Push — '
                f'Receipt: {receipt or "pending"} | '
                f'Checkout: {transaction.checkout_request_id}'
            ),
            status='Completed',
            receipt_number=receipt,
        )
        logger.info(
            "_fulfil: Payment created for user=%s checkout=%s receipt=%s",
            user.username, transaction.checkout_request_id, receipt,
        )
    else:
        logger.info(
            "_fulfil: Payment already exists for checkout=%s — skipping",
            transaction.checkout_request_id,
        )

    # ── 2 & 3 & 4. Cart → FeedOrders + stock deduction + cart clear ──────────
    cart = Cart.objects.filter(farmer=user).prefetch_related('items__feed').first()
    if cart and cart.items.exists():
        for item in cart.items.all():
            # Guard against duplicate orders for the same cart item / transaction
            if not FeedOrder.objects.filter(
                farmer=user,
                feed=item.feed,
                payment_source=transaction.checkout_request_id,
            ).exists():
                FeedOrder.objects.create(
                    farmer=user,
                    feed=item.feed,
                    quantity=item.quantity,
                    total_price=item.total_price,
                    status='Pending',
                    payment_method='M-Pesa',
                    payment_source=transaction.checkout_request_id,  # idempotency key
                )
                # Deduct stock (clamp to 0 to avoid negatives)
                item.feed.stock_quantity = max(
                    0, item.feed.stock_quantity - item.quantity
                )
                item.feed.save(update_fields=['stock_quantity'])

        cart.items.all().delete()
        logger.info(
            "_fulfil: FeedOrders created and cart cleared for user=%s",
            user.username,
        )
    else:
        logger.info(
            "_fulfil: Cart empty or already processed for user=%s — skipping orders",
            user.username,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 — Initiate STK Push
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def initiate_mpesa_payment(request):
    """Initiate an M-Pesa STK Push for the farmer's current cart."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    phone_number = request.POST.get('phone_number', '').strip()
    amount       = request.POST.get('amount', '').strip()
    use_test     = request.POST.get('use_test_mode', 'false').lower() == 'true'

    # ── Sandbox / test simulation ─────────────────────────────────────────────
    if use_test:
        import random
        receipt = f"TEST{random.randint(100000, 999999)}"

        # Create a completed dummy transaction so _fulfil can run
        fake_checkout_id = f"TEST-{request.user.id}-{int(time.time())}"
        txn = MpesaTransaction.objects.create(
            user=request.user,
            phone_number=phone_number or '254700000000',
            amount=amount,
            checkout_request_id=fake_checkout_id,
            status='COMPLETED',
            mpesa_receipt_number=receipt,
            date_completed=timezone.now(),
        )
        _fulfil_completed_transaction(txn, receipt_number=receipt)
        logger.info("Test payment fulfilled: receipt=%s user=%s", receipt, request.user.username)
        return JsonResponse({'success': True, 'receipt': receipt, 'test_mode': True})

    # ── Input validation ──────────────────────────────────────────────────────
    if not phone_number:
        return JsonResponse({'success': False, 'error': 'Phone number is required.'}, status=400)
    if not amount:
        return JsonResponse({'success': False, 'error': 'Amount is required.'}, status=400)

    _, phone_error = MpesaService.format_phone_number(phone_number)
    if phone_error:
        return JsonResponse({'success': False, 'error': phone_error}, status=400)

    # ── Real STK Push ─────────────────────────────────────────────────────────
    mpesa = MpesaService()
    response_data, error = mpesa.stk_push(phone_number, amount)

    if error:
        logger.error("STK Push error user=%s: %s", request.user.username, error)
        return JsonResponse({'success': False, 'error': error}, status=400)

    checkout_request_id = (
        response_data.get('CheckoutRequestID')
        or f"MPESA-{request.user.id}-{int(time.time())}"
    )

    mpesa.create_transaction(
        user=request.user,
        phone_number=phone_number,
        amount=amount,
        checkout_request_id=checkout_request_id,
    )

    logger.info(
        "STK Push initiated: user=%s phone=%s amount=%s checkout=%s",
        request.user.username, phone_number, amount, checkout_request_id,
    )
    return JsonResponse({
        'success': True,
        'message': 'STK Push sent. Enter your M-Pesa PIN on your phone.',
        'checkout_request_id': checkout_request_id,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 — Safaricom callback  (no CSRF — Safaricom POST hits this directly)
# ─────────────────────────────────────────────────────────────────────────────
@csrf_exempt
def mpesa_callback(request):
    """Receive STK Push result callback from Safaricom."""
    if request.method != 'POST':
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Method not allowed'}, status=405)

    try:
        data         = json.loads(request.body)
        stk_callback = data.get('Body', {}).get('stkCallback', {})

        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code         = stk_callback.get('ResultCode')
        result_desc         = stk_callback.get('ResultDesc', '')

        if not checkout_request_id:
            logger.error("Callback missing CheckoutRequestID: %s", data)
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing CheckoutRequestID'})

        mpesa = MpesaService()

        if result_code == 0:
            # ── Successful payment ────────────────────────────────────────────
            receipt_number = None
            paid_amount    = None

            for item in stk_callback.get('CallbackMetadata', {}).get('Item', []):
                name  = item.get('Name')
                value = item.get('Value')
                if name == 'MpesaReceiptNumber':
                    receipt_number = value
                elif name == 'Amount':
                    paid_amount = value

            transaction = mpesa.update_transaction(
                checkout_request_id=checkout_request_id,
                status='COMPLETED',
                result_code=str(result_code),
                result_desc=result_desc,
                mpesa_receipt_number=receipt_number,
                date_completed=timezone.now(),
            )

            if transaction:
                _fulfil_completed_transaction(transaction, receipt_number=receipt_number)

            logger.info(
                "Callback SUCCESS: checkout=%s receipt=%s amount=%s",
                checkout_request_id, receipt_number, paid_amount,
            )

        else:
            # ── Failed / cancelled ────────────────────────────────────────────
            # ResultCode 1032 = user cancelled, 1 = insufficient funds
            status = 'CANCELLED' if result_code == 1032 else 'FAILED'
            mpesa.update_transaction(
                checkout_request_id=checkout_request_id,
                status=status,
                result_code=str(result_code),
                result_desc=result_desc,
            )
            logger.info(
                "Callback %s: checkout=%s code=%s desc=%s",
                status, checkout_request_id, result_code, result_desc,
            )

        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    except json.JSONDecodeError as exc:
        logger.error("Callback JSON decode error: %s", exc)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'})
    except Exception as exc:
        logger.exception("Callback unexpected error: %s", exc)
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal error'})


# ─────────────────────────────────────────────────────────────────────────────
# Task 4 — Status polling endpoint  (called by the checkout JS every 4 s)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def check_payment_status(request, checkout_request_id):
    """
    Poll the status of a pending STK Push.

    Flow:
      1. Look up the local MpesaTransaction.
      2. If PENDING → ask Safaricom directly via STK query API.
      3. If Safaricom says COMPLETED → run _fulfil_completed_transaction so
         FeedOrders and Payment are created even if the callback never arrived.
      4. Return the current status as JSON to the polling JS.
    """
    mpesa       = MpesaService()
    transaction = mpesa.get_transaction(checkout_request_id)

    if not transaction:
        return JsonResponse({'error': 'Transaction not found'}, status=404)

    # Ownership guard
    if transaction.user != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # ── If still pending, ask Safaricom ──────────────────────────────────────
    if transaction.status == 'PENDING':
        query_data, query_error = mpesa.query_stk_push_status(checkout_request_id)

        if query_data and not query_error:
            remote_code = str(query_data.get('ResultCode', ''))

            if remote_code == '0':
                # Payment confirmed by Safaricom query
                receipt = query_data.get('MpesaReceiptNumber')  # may be absent in query response
                transaction = mpesa.update_transaction(
                    checkout_request_id=checkout_request_id,
                    status='COMPLETED',
                    result_code=remote_code,
                    result_desc=query_data.get('ResultDesc', ''),
                    mpesa_receipt_number=receipt,
                    date_completed=timezone.now(),
                )
                # ── Task 4 fix: fulfil here so FeedOrders are created
                #    even when the Safaricom callback never reaches us ─────────
                if transaction:
                    _fulfil_completed_transaction(transaction, receipt_number=receipt)

            elif remote_code not in ('', 'None'):
                # Any non-empty, non-zero code means failure
                status = 'CANCELLED' if remote_code == '1032' else 'FAILED'
                transaction = mpesa.update_transaction(
                    checkout_request_id=checkout_request_id,
                    status=status,
                    result_code=remote_code,
                    result_desc=query_data.get('ResultDesc', ''),
                )
        else:
            # Safaricom query failed (network, token issue) — stay PENDING,
            # the JS will retry in 4 s
            logger.warning(
                "STK query failed for checkout=%s: %s",
                checkout_request_id, query_error,
            )

    return JsonResponse({
        'status':      transaction.status,
        'receipt':     transaction.mpesa_receipt_number,
        'amount':      str(transaction.amount),
        'result_desc': transaction.result_desc,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Payment history  (JSON — used by payment-pending page)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def payment_history(request):
    """Return the authenticated user's M-Pesa transaction history as JSON."""
    mpesa        = MpesaService()
    transactions = mpesa.get_user_transactions(request.user)

    data = [
        {
            'checkout_request_id': t.checkout_request_id,
            'phone_number':        t.phone_number,
            'amount':              str(t.amount),
            'status':              t.status,
            'receipt':             t.mpesa_receipt_number,
            'date_requested':      t.date_requested.isoformat(),
            'date_completed':      t.date_completed.isoformat() if t.date_completed else None,
        }
        for t in transactions
    ]
    return JsonResponse({'transactions': data})


# ─────────────────────────────────────────────────────────────────────────────
# Payment-pending page  (Task 6 — rendered view, not JSON)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def payment_pending_page(request, checkout_request_id):
    """
    Fallback HTML page for farmers who navigated away during checkout.
    Shows live status and auto-redirects to My Orders when payment completes.
    """
    mpesa       = MpesaService()
    transaction = mpesa.get_transaction(checkout_request_id)

    if not transaction:
        messages.error(request, 'Transaction not found.')
        return redirect('farmer_app:my_orders')

    if transaction.user != request.user and not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('farmer_app:my_orders')

    return render(request, 'mpesa/payment_pending.html', {
        'transaction': transaction,
        'checkout_request_id': checkout_request_id,
    })
