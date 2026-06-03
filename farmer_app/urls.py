from django.urls import path
from . import views

app_name = 'farmer_app'

urlpatterns = [
    path('', views.farmer_dashboard, name='farmer_dashboard'),
    path('dashboard/', views.farmer_dashboard, name='farmer_dashboard'),
    
    # Milk Records
    path('milk-records/', views.milk_records, name='milk_records'),
    
    # Feeds
    path('feeds/', views.view_feeds, name='view_feeds'),
    path('feeds/order/<int:feed_id>/', views.order_feed, name='order_feed'),
    path('feeds/my-orders/', views.my_orders, name='my_orders'),
    path('feeds/cart/', views.view_cart, name='view_cart'),
    path('feeds/cart/add/<int:feed_id>/', views.add_to_cart, name='add_to_cart'),
    path('feeds/cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('feeds/cart/checkout/', views.checkout_cart, name='checkout_cart'),
    
    # Payments
    path('payments/', views.view_payments, name='view_payments'),
    path('payments/receipt/<int:payment_id>/', views.download_receipt, name='download_receipt'),
    
    # Reports
    path('reports/', views.my_reports, name='my_reports'),
    
    # Livestock
    path('livestock/', views.livestock_management, name='livestock_management'),
    path('livestock/add/', views.add_cow, name='add_cow'),
    path('livestock/edit/<int:cow_id>/', views.edit_cow, name='edit_cow'),
    path('livestock/health/<int:cow_id>/', views.health_history, name='health_history'),
    path('livestock/health/add/<int:cow_id>/', views.add_health_record, name='add_health_record'),
    
    # Claims
    path('claims/', views.my_claims, name='my_claims'),
    path('claims/new/', views.file_claim, name='file_claim'),
    path('claims/view/<int:claim_id>/', views.view_claim, name='view_claim'),
    
    # Notifications
    path('notifications/', views.view_notifications, name='view_notifications'),
    
    # Profile
    path('profile/', views.view_profile, name='view_profile'),
]