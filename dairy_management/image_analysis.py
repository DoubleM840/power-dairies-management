import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_cow_image(image_base64):
    """Analyze cow health from image - with intelligent fallbacks"""
    
    prompt = """
    You are a veterinary expert analyzing cow health from photos.
    Examine this image and provide:
    1. **Overall Health Assessment** - General condition
    2. **Visible Symptoms** - Any concerning signs
    3. **Recommendations** - Practical care advice
    4. **Urgency Level** - Whether immediate vet attention is needed
    
    Be specific and practical. Always recommend consulting a veterinarian for serious issues.
    """
    
    # Try vision models first
    vision_models = [
        "llama-3.2-11b-vision-preview",
    ]
    
    for model in vision_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=800,
                temperature=0.7
            )
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e).lower()
            if "decommissioned" in error_msg or "not found" in error_msg or "not supported" in error_msg:
                continue
            else:
                print(f"Image analysis error: {e}")
                return ask_user_for_description()
    
    # If all vision models fail, provide helpful text-based alternative
    return ask_user_for_description()


def ask_user_for_description():
    """Return a helpful message asking user to describe the cow"""
    return """**Vision Analysis Unavailable**

I'm unable to analyze images at the moment, but I can still help! Please describe the cow's condition:

**Please tell me:**
1. **Behavior** - Is the cow acting normally? Lethargic? Agitated?
2. **Appetite** - Eating and drinking normally?
3. **Physical signs** - Any visible swelling, discharge, limping, or skin issues?
4. **Milk production** - Any changes in milk yield or quality?
5. **Body condition** - Weight loss or gain?

Once you provide these details, I'll give you expert veterinary advice and recommendations!

**For urgent cases** (severe distress, inability to stand, heavy bleeding), please contact a veterinarian immediately."""