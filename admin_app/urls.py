from django.urls import path
from . import views

app_name = 'admin_app'

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/', views.admin_dashboard, name='dashboard'),
    path('notifications/', views.notifications, name='notifications'),
    
    # User Management
    path('users/', views.manage_users, name='manage_users'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'), # ADDED
    
    # Milk Overview
    path('milk/', views.milk_overview, name='milk_overview'),
    path('milk/edit/<int:record_id>/', views.edit_milk_record, name='edit_milk_record'),
    path('milk/summary/', views.milk_summary, name='milk_summary'),
    
    # Rates
    path('rates/', views.manage_rates, name='manage_rates'),
    path('rates/add/', views.add_rate, name='add_rate'),
    path('rates/edit/<int:rate_id>/', views.edit_rate, name='edit_rate'),
    
    # Payments (Separated into Feed Orders & Milk Payments)
    path('payments/', views.manage_payments, name='manage_payments'),
    path('payments/approve/<int:payment_id>/', views.approve_payment, name='approve_payment'),
    path('payments/reject/<int:payment_id>/', views.reject_payment, name='reject_payment'),
    
    # Feeds
    path('feeds/', views.manage_feeds, name='manage_feeds'),
    path('feeds/add/', views.add_feed, name='add_feed'),
    path('feeds/edit/<int:feed_id>/', views.edit_feed, name='edit_feed'),
    path('feeds/delete/<int:feed_id>/', views.delete_feed, name='delete_feed'),
    path('feeds/orders/', views.feed_orders_summary, name='feed_orders_summary'),
    
    # Claims
    path('claims/', views.manage_claims, name='manage_claims'),
    path('claims/review/<int:claim_id>/', views.review_claim, name='review_claim'),
    path('claims/approve/<int:claim_id>/', views.approve_claim, name='approve_claim'),
    path('claims/reject/<int:claim_id>/', views.reject_claim, name='reject_claim'),
    
    # Collector Allocation
    path('allocate-collectors/', views.allocate_collectors, name='allocate_collectors'),
    path('allocate-collectors/add/', views.add_allocation, name='add_allocation'),
    path('allocate-collectors/delete/<int:allocation_id>/', views.delete_allocation, name='delete_allocation'),
]