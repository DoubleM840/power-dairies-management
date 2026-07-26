from django.urls import path
from . import views

app_name = 'mpesa'

urlpatterns = [
    # Initiate STK Push (AJAX POST from checkout page)
    path('initiate/',                             views.initiate_mpesa_payment, name='initiate_payment'),

    # Safaricom callback — must be publicly reachable (ngrok/Railway URL)
    path('callback/',                             views.mpesa_callback,         name='callback'),

    # Status polling (AJAX GET from checkout JS, every 4 s)
    path('status/<str:checkout_request_id>/',     views.check_payment_status,   name='check_status'),

    # Fallback HTML page — for farmers who navigate away mid-payment
    path('pending/<str:checkout_request_id>/',    views.payment_pending_page,   name='payment_pending'),

    # Transaction history (JSON)
    path('history/',                              views.payment_history,         name='payment_history'),
]
