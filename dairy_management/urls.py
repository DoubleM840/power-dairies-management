from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect  # <-- THIS IMPORT WAS MISSING

urlpatterns = [
    path('django-admin/', admin.site.urls),
    
    # Redirect root URL to the login page
    path('', lambda request: redirect('accounts:login'), name='home'),
    
    # Redirect generic /dashboard/ to the smart dashboard router
    path('dashboard/', lambda request: redirect('accounts:dashboard'), name='main_dashboard'),
    
    # App URLs
    path('accounts/', include('accounts.urls')),
    path('admin-app/', include('admin_app.urls')),
    path('collector-app/', include('collector_app.urls')),
    path('farmer-app/', include('farmer_app.urls')),
]

# Serve media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)