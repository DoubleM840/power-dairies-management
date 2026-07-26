from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import base64

from .models import UserProfile, ChatSession, ChatMessage
from dairy_management.chatbot import get_ai_response
from dairy_management.image_analysis import analyze_cow_image


def get_or_create_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def login_view(request):
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
    try:
        demo_user = User.objects.get(username='demo_farmer')
        login(request, demo_user)
        get_or_create_profile(demo_user)
        messages.info(request, 'You are now in demo mode.')
        return redirect('farmer_app:farmer_dashboard')
    except User.DoesNotExist:
        messages.error(request, 'Demo account not available.')
        return redirect('accounts:login')


def register_farmer(request):
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
            
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name, is_active=True)
            profile = get_or_create_profile(user)
            profile.role = 'farmer'
            profile.phone = phone
            profile.address = address
            profile.is_approved = True
            profile.save()
            
            messages.success(request, f'Registration successful! Farmer ID: {getattr(profile, "farmer_number", "N/A")}')
            return redirect('accounts:login')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'accounts/register_farmer.html')
    return render(request, 'accounts/register_farmer.html')


def register_collector(request):
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
            
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name, is_active=True)
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
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


# ==================== CHATBOT & AI VIEWS ====================

@login_required
@csrf_exempt
def get_chat_history(request):
    try:
        sessions = ChatSession.objects.filter(user=request.user, is_active=True)[:20]
        history = [{
            'id': session.id,
            'title': session.title,
            'created_at': session.created_at.strftime('%Y-%m-%d %H:%M'),
            'message_count': session.messages.count()
        } for session in sessions]
        return JsonResponse({'history': history})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_exempt
def create_new_chat(request):
    try:
        session = ChatSession.objects.create(user=request.user, title="New Conversation", is_active=True)
        return JsonResponse({'success': True, 'session_id': session.id, 'title': session.title})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_exempt
def load_chat_session(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        chat_messages = [{
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M')
        } for msg in session.messages.all()]
        return JsonResponse({'session_id': session.id, 'title': session.title, 'messages': chat_messages})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

@login_required
@csrf_exempt
def delete_chat_session(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.delete()
        return JsonResponse({'success': True})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

@csrf_exempt
def chat_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            language = data.get('language', 'en')
            session_id = data.get('session_id')
            
            if request.user.is_authenticated:
                user_id = f"user_{request.user.id}"
            else:
                user_id = f"session_{request.session.session_key or 'anonymous'}"
            
            if not user_message.strip():
                return JsonResponse({'response': 'Please type a question.'})
            
            session = None
            if session_id and request.user.is_authenticated:
                try:
                    session = ChatSession.objects.get(id=session_id, user=request.user)
                except ChatSession.DoesNotExist:
                    session = None
            
            if not session and request.user.is_authenticated:
                session = ChatSession.objects.create(
                    user=request.user,
                    title=user_message[:50] + "..." if len(user_message) > 50 else user_message
                )
            
            if session:
                ChatMessage.objects.create(session=session, role='user', content=user_message)
            
            ai_response = get_ai_response(user_message, user_id, language)
            
            if session:
                ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
                if session.messages.count() == 2:
                    session.title = user_message[:50] + "..." if len(user_message) > 50 else user_message
                    session.save()
            
            return JsonResponse({
                'response': ai_response,
                'language': language,
                'session_id': session.id if session else None
            })
        except Exception as e:
            print(f"Chatbot error: {e}")
            return JsonResponse({'response': 'Sorry, I encountered an error.'}, status=500)
    return JsonResponse({'response': 'Invalid request'}, status=400)

@csrf_exempt
def analyze_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            analysis = analyze_cow_image(image_base64)
            return JsonResponse({'analysis': analysis})
        except Exception as e:
            print(f"Image upload error: {e}")
            return JsonResponse({'error': 'Failed to analyze image'}, status=500)
    return JsonResponse({'error': 'No image provided'}, status=400)