import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
for m in genai.list_models():
    print(m.name, m.supported_generation_methods)

model = genai.GenerativeModel("models/gemini-2.5-flash")

def review_code(prompt: str) -> str:
    response = model.generate_content(prompt)
    return response.text
