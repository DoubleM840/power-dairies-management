from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('admin-app/', include('admin_app.urls')),
    path('farmer-app/', include('farmer_app.urls')),
    path('collector-app/', include('collector_app.urls')),
    path('mpesa/', include('mpesa.urls')),
    
    # Chatbot & AI URLs - move these to a chatbot app
    path('api/chat/', include('chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)