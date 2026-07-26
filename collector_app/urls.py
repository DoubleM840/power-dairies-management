from django.urls import path
from . import views

app_name = 'collector_app'

urlpatterns = [
    path('dashboard/', views.collector_dashboard, name='collector_dashboard'),
    path('collect-milk/', views.collect_milk, name='collect_milk'),
    path('milk-records/', views.milk_records, name='milk_records'),
    path('payments/', views.view_payments, name='view_payments'),
    path('payments/commission-slip/', views.download_commission_slip, name='commission_slip'),
    path('payments/commission-slip/<str:month>/', views.download_commission_slip, name='commission_slip_month'),
    path('farmers/', views.view_farmers, name='view_farmers'),
    path('profile/', views.view_profile, name='view_profile'),
    path('notifications/', views.view_notifications, name='view_notifications'),
]