from django.urls import path
from . import views

app_name = 'mpesa'

urlpatterns = [
    path('initiate/', views.initiate_mpesa_payment, name='initiate_payment'),
    path('callback/', views.mpesa_callback, name='callback'),
    path('status/<str:checkout_request_id>/', views.check_payment_status, name='check_status'),
]