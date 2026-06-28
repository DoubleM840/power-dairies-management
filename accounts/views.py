from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile
from django.contrib.auth.decorators import login_required


def get_or_create_profile(user):
    """Safely get or create a user profile"""
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def login_view(request):
    # If user is already logged in, redirect them
    if request.user.is_authenticated:
        try:
            profile = get_or_create_profile(request.user)
            role = profile.role
            
            if role == 'admin':
                return redirect('admin_app:admin_dashboard')
            elif role == 'collector':
                if not profile.is_approved:
                    messages.warning(request, 'Your collector account is pending admin approval.')
                    logout(request)
                    return redirect('accounts:login')
                return redirect('collector_app:collector_dashboard')
            elif role == 'farmer':
                return redirect('farmer_app:farmer_dashboard')
        except Exception as e:
            logout(request)
            messages.error(request, f'Error: {str(e)}')
    
    # Handle POST request
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            
            try:
                profile = get_or_create_profile(user)
                role = profile.role
                
                if role == 'admin':
                    return redirect('admin_app:admin_dashboard')
                elif role == 'collector':
                    if not profile.is_approved:
                        messages.warning(request, 'Your account is pending approval.')
                        logout(request)
                        return redirect('accounts:login')
                    return redirect('collector_app:collector_dashboard')
                elif role == 'farmer':
                    return redirect('farmer_app:farmer_dashboard')
            except Exception as e:
                messages.error(request, f'Profile error: {str(e)}')
                logout(request)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')


def smart_dashboard(request):
    """Smart dashboard that redirects based on user role"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    try:
        profile = get_or_create_profile(request.user)
        role = profile.role
        
        if role == 'admin':
            return redirect('admin_app:admin_dashboard')
        elif role == 'collector':
            if not profile.is_approved:
                messages.warning(request, 'Your account is pending approval.')
                logout(request)
                return redirect('accounts:login')
            return redirect('collector_app:collector_dashboard')
        elif role == 'farmer':
            return redirect('farmer_app:farmer_dashboard')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        logout(request)
    
    return redirect('accounts:login')


def demo_login(request):
    """Auto-login demo user"""
    try:
        demo_user = User.objects.get(username='demo_farmer')
        login(request, demo_user)
        get_or_create_profile(demo_user)  # Ensure profile exists
        messages.info(request, 'You are now in demo mode.')
        return redirect('farmer_app:farmer_dashboard')
    except User.DoesNotExist:
        messages.error(request, 'Demo account not available.')
        return redirect('accounts:login')


def register_farmer(request):
    """Register new farmer account"""
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
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            # Profile is auto-created by signal, just update it
            profile = get_or_create_profile(user)
            profile.role = 'farmer'
            profile.phone = phone
            profile.address = address
            profile.is_approved = True
            profile.save()
            
            messages.success(request, f'Registration successful! Farmer ID: {profile.farmer_number}')
            return redirect('accounts:login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'accounts/register_farmer.html')
    
    return render(request, 'accounts/register_farmer.html')


def register_collector(request):
    """Register new collector account"""
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
            
            if not username or not email or not password:
                messages.error(request, 'All required fields must be filled.')
                return render(request, 'accounts/register_collector.html')
            
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'accounts/register_collector.html')
            
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                return render(request, 'accounts/register_collector.html')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return render(request, 'accounts/register_collector.html')
            
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already registered.')
                return render(request, 'accounts/register_collector.html')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            profile = get_or_create_profile(user)
            profile.role = 'collector'
            profile.phone = phone
            profile.address = address
            profile.is_approved = False
            profile.save()
            
            messages.success(request, 'Registration successful! Account pending admin approval.')
            return redirect('accounts:login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'accounts/register_collector.html')
    
    return render(request, 'accounts/register_collector.html')


@login_required
def logout_view(request):
    """Logout user"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')