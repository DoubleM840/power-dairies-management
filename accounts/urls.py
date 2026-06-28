from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('demo-login/', views.demo_login, name='demo_login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.smart_dashboard, name='dashboard'),
    path('register/farmer/', views.register_farmer, name='register_farmer'),
    path('register/collector/', views.register_collector, name='register_collector'),  # ADD THIS LINE
]