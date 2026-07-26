from django.urls import path
from . import views

urlpatterns = [
    path('chat/',                          views.chat_api,          name='chat_api'),
    path('analyze-image/',                 views.analyze_image_api, name='analyze_image_api'),
    path('chat-history/',                  views.chat_history_api,  name='chat_history_api'),
    path('load-chat/<int:session_id>/',    views.load_chat_api,     name='load_chat_api'),
    path('delete-chat/<int:session_id>/',  views.delete_chat_api,   name='delete_chat_api'),
    path('weather/',                       views.weather_api,        name='weather_api'),
]
