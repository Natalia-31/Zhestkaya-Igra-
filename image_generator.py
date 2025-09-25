import random
from pathlib import Path
from typing import Optional
import requests
import base64
import os

# сюда ВСТАВЛЯЕШЬ свой ключ от Gemini!
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"  # ← Сюда вставь ключ из Google AI Studio

# адрес для Gemini image API
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"

# папка для картинок
GENERATED_DIR = Path(__file__).parent / "generated_images"
GENERATED_DIR.mkdir(exist_ok=True)

def generate_image_via_gemini(situation: str, answer: str) -> Optional[bytes]:
    prompt = (
        f"Сгенерируй digital board game card изображение для ситуации: '{situation}'. "
        f"Ответ: '{answer}'. Стиль: русская настольная игра, минимализм, юмор, Russian language."
    )
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        r = requests.post(GEMINI_URL, headers=headers, json=data)
        r.raise_for_status()
        response_json = r.json()
        print("Gemini response:", response_json)  # ← А тут будет весь ответ Gemini!
        parts = (
            response_json.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        for part in parts:
            if "inlineData" in part and "data" in part["inlineData"]:
                img_b64 = part["inlineData"]["data"]
                return base64.b64decode(img_b64)
        print("Картинка не найдена в ответе Gemini.")
        return None
    except Exception as e:
        print("Ошибка Gemini генерации:", e)
        return None

def create_card(situation: str, answer: str) -> Optional[Path]:
    filename = f"{random.randint(0,999999)}.png"
    out_path = GENERATED_DIR / filename
    img_bytes = generate_image_via_gemini(situation, answer)
    if img_bytes:
        out_path.write_bytes(img_bytes)
        print(f"Карточка сохранена: {out_path}")
        return out_path
    else:
        print("Не удалось получить картинку от Gemini!")
        return None

if __name__ == "__main__":
    # Пример теста!
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"
    create_card(situation, answer)
