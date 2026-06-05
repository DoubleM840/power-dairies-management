from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from .models import UserProfile
from django.utils import timezone
from django.contrib.auth.decorators import login_required


def smart_dashboard(request):
    """Smart dashboard that redirects based on user role"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    return redirect_to_dashboard(request.user)


def login_view(request):
    """Clean login view - no approval check"""
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            try:
                profile = user.profile
                if not profile.is_active_account:
                    messages.error(request, 'Account is deactivated. Contact support.')
                    return render(request, 'accounts/login.html')
                
                profile.last_login = timezone.now()
                profile.save(update_fields=['last_login'])
                
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(user=user)
            
            login(request, user)
            return redirect_to_dashboard(user)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')

def demo_login(request):
    """Auto-login demo user"""
    from django.contrib.auth import login
    from django.contrib.auth.models import User
    
    try:
        demo_user = User.objects.get(username='demo_farmer')
        login(request, demo_user)
        messages.info(request, 'You are now in demo mode. Some features are limited.')
        return redirect('farmer_app:farmer_dashboard')
    except User.DoesNotExist:
        messages.error(request, 'Demo account not available.')
        return redirect('accounts:login')


def redirect_to_dashboard(user):
    """Redirect based on user role"""
    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return redirect('accounts:login')
    
    redirects = {
        'admin': 'admin_app:admin_dashboard',
        'collector': 'collector_app:collector_dashboard',
        'farmer': 'farmer_app:farmer_dashboard',
    }
    
    return redirect(redirects.get(role, 'accounts:login'))


def register_farmer(request):
    """Register new farmer account - IMMEDIATE ACCESS (no approval needed)"""
    if request.method == 'POST':
        try:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()
            
            # Validation
            if not username or not email or not password:
                messages.error(request, 'All required fields must be filled.')
                return render(request, 'accounts/register_farmer.html')
            
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'accounts/register_farmer.html')
            
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                return render(request, 'accounts/register_farmer.html')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return render(request, 'accounts/register_farmer.html')
            
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already registered.')
                return render(request, 'accounts/register_farmer.html')
            
            # 1. Create user with is_active=True (IMMEDIATE ACCESS)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True  # IMMEDIATE ACCESS - no approval needed
            )
            
            # 2. Generate UNIQUE farmer number using timestamp + user ID
            now = timezone.now()
            timestamp = now.strftime('%H%M%S%f')
            farmer_number = f'FRM-{now.year}-{timestamp}{user.id}'
            
            # Update the profile
            profile = user.profile
            profile.role = 'farmer'
            profile.phone = phone
            profile.address = address
            profile.farmer_number = farmer_number
            profile.save()
            
            # 3. Show success message
            messages.success(
                request, 
                f'Registration successful! Your Farmer ID is: {farmer_number}. '
                f'You can now login and access your dashboard.'
            )
            return redirect('accounts:login')
            
        except Exception as e:
            messages.error(request, f'Registration failed. Please try again.')
            return render(request, 'accounts/register_farmer.html')
    
    return render(request, 'accounts/register_farmer.html')


# NOTE: register_collector has been REMOVED. Collectors are now created exclusively by the Admin.


@login_required
def logout_view(request):
    """Logout user"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')