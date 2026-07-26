import os
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key
API_KEY = os.getenv("GROQ_API_KEY")

if API_KEY and API_KEY.startswith("gsk_"):
    pass  # Key loaded successfully
else:
    import sys
    print("WARNING: Groq API Key not found or invalid!", file=sys.stderr)

# Initialize Groq client
if API_KEY:
    try:
        client = Groq(api_key=API_KEY)
    except Exception as e:
        import sys
        print(f"WARNING: Groq client init error: {e}", file=sys.stderr)
        client = None
else:
    client = None

# System prompts for different languages
SYSTEM_PROMPT_EN = """
You are "DairyBot", a knowledgeable agricultural assistant for Power Dairies Management System.

Expertise:
- Dairy farming: animal nutrition, disease management, milk production
- Feed management: types, schedules, storage
- System guidance: platform features navigation
- Weather-aware farming advice

Be friendly, concise, and practical. Recommend veterinarians for serious health issues.
Respond in ENGLISH.
"""

SYSTEM_PROMPT_SW = """
You are "DairyBot", msaidizi wa kilimo cha maziwa kwa Power Dairies Management System.

Utaalamu:
- Ufugaji wa ng'ombe: lishe, udhibiti wa magonjwa, uzalishaji wa maziwa
- Usimamizi wa chakula: aina, ratiba, uhifadhi
- Mwongozo wa mfumo: jinsi ya kutumia vipengele vya mfumo
- Ushauri wa kilimo kulingana na hali ya hewa

Kuwa rafiki, fupi, na vitendo. Pendekeza daktari wa wanyama kwa matatizo makubwa.
Jibu kwa KISWAHILI.
"""

# Store conversation history
conversation_history = {}

def get_user_conversation(user_id, language='en'):
    """Get or create conversation history for user"""
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    # Set system prompt based on language
    system_prompt = SYSTEM_PROMPT_SW if language == 'sw' else SYSTEM_PROMPT_EN
    
    # If no messages yet or language changed, reset with new system prompt
    if not conversation_history[user_id] or conversation_history[user_id][0]['role'] != 'system':
        conversation_history[user_id] = [
            {"role": "system", "content": system_prompt}
        ]
    else:
        # Update system prompt if language changed
        conversation_history[user_id][0]['content'] = system_prompt
    
    return conversation_history[user_id]

def add_to_conversation(user_id, role, message):
    """Add message to conversation history"""
    history = get_user_conversation(user_id)
    history.append({"role": role, "content": message})
    
    # Keep only last 10 messages to avoid token limits
    if len(history) > 11:  # 1 system + 10 messages
        history.pop(1)  # Remove oldest user message

def get_ai_response(user_message, user_id="anonymous", language="en"):
    """Generate AI response with language support"""
    if not client:
        return "Chatbot is not configured. Please add GROQ_API_KEY to .env file."
    
    try:
        # Get conversation history with correct language
        messages = get_user_conversation(user_id, language)
        
        # Add user message
        add_to_conversation(user_id, "user", user_message)
        
        # Get updated messages
        messages = get_user_conversation(user_id, language)
        
        # Generate response
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content
        
        # Add AI response to history
        add_to_conversation(user_id, "assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        print(f"Groq Error: {e}")
        return f"Sorry, I encountered an error. Please try again."