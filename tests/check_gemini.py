import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"API Key found: {'Yes' if api_key else 'No'}")

if api_key:
    genai.configure(api_key=api_key)
    try:
        print("Listing models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error listing models: {e}")
        
    print("\nTesting gemini-1.5-flash...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error with gemini-1.5-flash: {e}")
        
    print("\nTesting gemini-pro...")
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Hello")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error with gemini-pro: {e}")
