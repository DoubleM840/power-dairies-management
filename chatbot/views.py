import os
import base64
import json
import requests as http_requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from groq import Groq
from dotenv import load_dotenv
from .models import ChatSession, ChatMessage

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

# ── System prompts ────────────────────────────────────────────────────────────
SYSTEM_PROMPT_EN = (
    "You are 'DairyBot', a knowledgeable agricultural assistant for Power Dairies "
    "Management System. Expertise: dairy farming, animal nutrition, disease "
    "management, milk production, feed management, system guidance. "
    "Be friendly, concise, and practical. Recommend a veterinarian for serious "
    "health issues. Respond in ENGLISH."
)
SYSTEM_PROMPT_SW = (
    "Wewe ni 'DairyBot', msaidizi wa kilimo cha maziwa kwa Power Dairies. "
    "Utaalamu: ufugaji wa ng'ombe, lishe, udhibiti wa magonjwa, uzalishaji wa maziwa, "
    "usimamizi wa chakula. Kuwa rafiki, fupi, na vitendo. "
    "Pendekeza daktari wa wanyama kwa matatizo makubwa. Jibu kwa KISWAHILI."
)

def _system_prompt(language, weather_context=None):
    base = SYSTEM_PROMPT_SW if language == 'sw' else SYSTEM_PROMPT_EN
    if weather_context:
        base += f"\n\nCurrent local weather: {weather_context}"
    return base


def _vision_fallback():
    return (
        "**Vision Analysis Unavailable**\n\n"
        "Please describe the cow's condition:\n"
        "1. **Behavior** — Acting normally? Lethargic?\n"
        "2. **Appetite** — Eating and drinking normally?\n"
        "3. **Physical signs** — Swelling, discharge, limping, skin issues?\n"
        "4. **Milk production** — Changes in yield or quality?\n\n"
        "**For urgent cases** (severe distress, inability to stand, heavy bleeding), "
        "contact a veterinarian immediately."
    )


# ── Weather helper (Open-Meteo — no API key required) ────────────────────────
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "icy fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "heavy rain showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}

def _fetch_weather(lat="-1.2921", lon="36.8219"):
    """Fetch current weather from Open-Meteo (free, no key needed).
    Defaults to Nairobi. Returns a plain-English description string."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,"
            f"precipitation,wind_speed_10m,weathercode"
            f"&timezone=Africa%2FNairobi&forecast_days=1"
        )
        r = http_requests.get(url, timeout=5)
        r.raise_for_status()
        c = r.json().get("current", {})
        code = c.get("weathercode", 0)
        desc = WMO_CODES.get(code, "unknown")
        temp = c.get("temperature_2m", "?")
        humidity = c.get("relative_humidity_2m", "?")
        wind = c.get("wind_speed_10m", "?")
        rain = c.get("precipitation", 0)
        return {
            "description": desc,
            "temperature_c": temp,
            "humidity_pct": humidity,
            "wind_kmh": wind,
            "precipitation_mm": rain,
            "summary": (
                f"{desc.capitalize()}, {temp}°C, humidity {humidity}%, "
                f"wind {wind} km/h, precipitation {rain} mm"
            ),
        }
    except Exception:
        return None


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def chat_api(request):
    if not client:
        return JsonResponse({
            'response': 'Chatbot not configured. Add GROQ_API_KEY to .env',
            'session_id': None,
        })

    data = json.loads(request.body)
    message = data.get('message', '').strip()
    language = data.get('language', 'en')
    session_id = data.get('session_id')
    weather_context = data.get('weather_context')  # optional — passed from the widget

    if not message:
        return JsonResponse({'response': 'Empty message.', 'session_id': session_id})

    system_prompt = _system_prompt(language, weather_context)

    # ── Resolve session ───────────────────────────────────────────────────────
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            session = None
    else:
        session = None

    if session is None:
        title = message[:50] + ("…" if len(message) > 50 else "")
        session = ChatSession.objects.create(user=request.user, title=title)
        ChatMessage.objects.create(session=session, role='system', content=system_prompt)

    # ── Build message history (last 20 messages for context) ─────────────────
    db_msgs = list(
        session.messages.order_by('timestamp').values('role', 'content')[:21]
    )
    # Always keep/refresh the system prompt at position 0
    if db_msgs and db_msgs[0]['role'] == 'system':
        db_msgs[0] = {'role': 'system', 'content': system_prompt}
    else:
        db_msgs.insert(0, {'role': 'system', 'content': system_prompt})

    db_msgs.append({'role': 'user', 'content': message})

    # Persist the user message
    ChatMessage.objects.create(session=session, role='user', content=message)

    # ── Call Groq ─────────────────────────────────────────────────────────────
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=db_msgs,
            temperature=0.7,
            max_tokens=600,
        )
        ai_response = resp.choices[0].message.content
        ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
        return JsonResponse({'response': ai_response, 'session_id': session.id})
    except Exception as e:
        return JsonResponse(
            {'response': 'Sorry, I encountered an error. Please try again.',
             'session_id': session.id},
            status=500,
        )


@login_required
@require_POST
def analyze_image_api(request):
    if not client:
        return JsonResponse({'analysis': 'Chatbot not configured.'}, status=503)

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'analysis': 'No image provided.'}, status=400)

    if image_file.size > 10 * 1024 * 1024:
        return JsonResponse({'analysis': 'Image too large. Max 10 MB.'}, status=400)

    image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    mime = image_file.content_type or 'image/jpeg'

    prompt = (
        "You are a veterinary expert analyzing cow health from photos. "
        "Examine the image carefully and provide:\n"
        "1. **Overall Health Assessment** — General body condition\n"
        "2. **Visible Symptoms** — Any concerning signs (coat, eyes, posture, limbs)\n"
        "3. **Recommendations** — Practical care steps the farmer should take\n"
        "4. **Urgency Level** — Low / Medium / High — and whether a vet is needed\n\n"
        "Be specific and practical."
    )

    vision_models = [
        "llama-3.2-11b-vision-preview",
        "llama-3.2-90b-vision-preview",
    ]

    for model in vision_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime};base64,{image_base64}"
                        }},
                    ],
                }],
                max_tokens=800,
                temperature=0.7,
            )
            return JsonResponse({'analysis': response.choices[0].message.content})
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ('decommissioned', 'not found', 'not supported', 'model')):
                continue
            break

    return JsonResponse({'analysis': _vision_fallback()})


@login_required
@require_GET
def chat_history_api(request):
    sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:50]
    history = [
        {
            'id': s.id,
            'title': s.title,
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M'),
            'message_count': s.messages.exclude(role='system').count(),
        }
        for s in sessions
    ]
    return JsonResponse({'history': history})


@login_required
@require_GET
def load_chat_api(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = [
            {'role': m['role'], 'content': m['content']}
            for m in session.messages.order_by('timestamp').values('role', 'content')
            if m['role'] != 'system'
        ]
        return JsonResponse({'session_id': session.id, 'messages': messages})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
@require_http_methods(["DELETE"])
def delete_chat_api(request, session_id):
    try:
        ChatSession.objects.get(id=session_id, user=request.user).delete()
        return JsonResponse({'success': True})
    except ChatSession.DoesNotExist:
        return JsonResponse({'success': False}, status=404)


@login_required
@require_GET
def weather_api(request):
    """Return current weather for the given coordinates (default: Nairobi)."""
    lat = request.GET.get('lat', '-1.2921')
    lon = request.GET.get('lon', '36.8219')
    weather = _fetch_weather(lat, lon)
    if weather:
        return JsonResponse({'ok': True, 'weather': weather})
    return JsonResponse({'ok': False, 'error': 'Could not fetch weather data'}, status=503)
