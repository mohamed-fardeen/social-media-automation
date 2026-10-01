import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load environment variables from backend/.env if available
env_path = Path(__file__).parent / "backend" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_TEXT_API_KEY") or os.getenv("GEMINI_IMAGE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else genai.Client()

def list_gemini_models():
    print("--- Querying ModelService.ListModels ---\n")
    
    # Calls the ModelService.ListModels endpoint
    models_pager = client.models.list()
    
    for model in models_pager:
        methods = getattr(model, "supported_generation_methods", None) or getattr(model, "supported_actions", None)
        print(f"Model ID : {model.name}")
        print(f"Display  : {getattr(model, 'display_name', '')}")
        if methods:
            print(f"Methods  : {methods}")
        print("-" * 50)

if __name__ == "__main__":
    list_gemini_models()