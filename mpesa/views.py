from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .services import MpesaService
from .models import MpesaTransaction
from farmer_app.models import Payment, FeedOrder, Cart
import json

@login_required
def initiate_mpesa_payment(request):
    """Initiate M-Pesa STK Push"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        amount = request.POST.get('amount')
        use_test_mode = request.POST.get('use_test_mode') == 'true'
        
        # Test mode - simulate payment
        if use_test_mode:
            import random
            receipt = f"MPESA{random.randint(100000, 999999)}"
            
            # Create payment record
            payment = Payment.objects.create(
                user=request.user,
                payment_type='feed_order',
                amount=amount,
                method='M-Pesa (Test)',
                description=f'Test M-Pesa payment',
                status='Completed',
                receipt_number=receipt
            )
            
            # Clear cart
            cart = Cart.objects.filter(farmer=request.user).first()
            if cart:
                cart.items.all().delete()
            
            messages.success(request, f'Test M-Pesa Payment of KES {amount} successful! Receipt: {receipt}')
            return JsonResponse({'success': True, 'receipt': receipt, 'test_mode': True})
        
        # Real M-Pesa payment
        mpesa_service = MpesaService()
        checkout_request_id = f"MPESA{request.user.id}{int(__import__('time').time())}"
        
        # Initiate STK Push
        response_data, error = mpesa_service.stk_push(phone_number, amount, checkout_request_id)
        
        if error:
            return JsonResponse({'success': False, 'error': error}, status=400)
        
        # Create transaction record
        mpesa_service.create_transaction(
            user=request.user,
            phone_number=phone_number,
            amount=amount,
            checkout_request_id=checkout_request_id
        )
        
        return JsonResponse({
            'success': True,
            'message': 'STK Push sent. Please enter your M-Pesa PIN.',
            'checkout_request_id': checkout_request_id
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def mpesa_callback(request):
    """M-Pesa callback URL - receives STK Push response"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            stk_callback = data.get('Body', {}).get('stkCallback', {})
            
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            mpesa_service = MpesaService()
            
            if result_code == 0:
                # Payment successful
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                # Extract receipt number and amount
                receipt_number = None
                amount = None
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        receipt_number = item.get('Value')
                    elif item.get('Name') == 'Amount':
                        amount = item.get('Value')
                
                # Update transaction
                transaction = mpesa_service.update_transaction(
                    checkout_request_id=checkout_request_id,
                    status='COMPLETED',
                    result_code=result_code,
                    result_desc=result_desc,
                    mpesa_receipt_number=receipt_number,
                    date_completed=__import__('django.utils.timezone').timezone.now()
                )
                
                # Create payment record if transaction exists
                if transaction:
                    Payment.objects.create(
                        user=transaction.user,
                        payment_type='feed_order',
                        amount=transaction.amount,
                        method='M-Pesa',
                        description=f'M-Pesa payment - Receipt: {receipt_number}',
                        status='Completed',
                        receipt_number=receipt_number
                    )
                    
                    # Clear cart
                    cart = Cart.objects.filter(farmer=transaction.user).first()
                    if cart:
                        cart.items.all().delete()
                
            else:
                # Payment failed/cancelled
                mpesa_service.update_transaction(
                    checkout_request_id=checkout_request_id,
                    status='FAILED' if result_code == 1 else 'CANCELLED',
                    result_code=result_code,
                    result_desc=result_desc
                )
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        except Exception as e:
            print(f"Callback error: {e}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Error processing callback'})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def check_payment_status(request, checkout_request_id):
    """Check M-Pesa payment status"""
    try:
        transaction = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
        
        return JsonResponse({
            'status': transaction.status,
            'receipt': transaction.mpesa_receipt_number,
            'amount': str(transaction.amount)
        })
    except MpesaTransaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction not found'}, status=404)