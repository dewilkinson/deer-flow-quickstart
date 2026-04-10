import os
import google.generativeai as genai

def list_models():
    api_key = os.environ.get("REASONING_MODEL__api_key") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: No API key found in environment.")
        return

    genai.configure(api_key=api_key)
    
    print("--- Available Gemini Models ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model: {m.name} (Display: {m.display_name})")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    list_models()
