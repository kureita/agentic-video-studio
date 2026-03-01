import os
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "apps/api/.env"))
api_key = os.environ.get("GOOGLE_AI_KEY") or os.environ.get("GEMINI_API_KEY")

if api_key:
    os.environ["GEMINI_API_KEY"] = api_key
    client = genai.Client()
    print("Available Gemini Models:")
    try:
        models = client.models.list()
        for m in models:
            if "3.1" in m.name or "3" in m.name or "2.5" in m.name:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("NO API KEY FOUND in .env")
