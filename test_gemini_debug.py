import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

models_to_try = [
    'gemini-pro',
    'gemini-1.5-pro', 
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-pro-latest'
]

print("Testing Google Gemini API...\n")

for model_name in models_to_try:
    try:
        print(f"Trying model: {model_name}")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say 'Hello' in one word")
        print(f"✅ SUCCESS with {model_name}")
        print(f"Response: {response.text.strip()}\n")
        break
    except Exception as e:
        print(f"❌ FAILED: {str(e)}\n")

# List available models
print("\nListing available models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"  - {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
