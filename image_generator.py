import requests
import google.generativeai as genai
import urllib.parse
import time
import random

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"
genai.configure(api_key=GEMINI_API_KEY)

# Для текстовой генерации — Gemini 2.5 Flash Lite
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

# 2. Улучшенная генерация визуального промпта
def refine_visual_prompt(situation, answer):
    prompt = (
        f"Situation: {situation}. Player answer: {answer}. "
        f"Create short English scene description for image generation. "
        f"Focus: character, action, atmosphere. Style: cartoon, board game art, minimalism. "
        f"Output only scene description, maximum 15 words."
    )
    try:
        response = gemini_model.generate_content(prompt)
        text = response.text.strip() if response and response.text else ""
        if not text or len(text) > 200:
            text = f"Cartoon board game illustration, {situation}, {answer}"
        return text
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
        return f"Cartoon board game illustration, {situation}, {answer}"

# 3. Улучшенная генерация картинки через Pollinations с retry логикой
def generate_pollinations_image(situation, answer, max_retries=3):
    visual_prompt = refine_visual_prompt(situation, answer)
    print(f"[Visual prompt]: {visual_prompt}")

    # Кодируем промпт для URL
    encoded_prompt = urllib.parse.quote(visual_prompt)

    # Различные варианты API endpoints
    endpoints = [
        f"https://image.pollinations.ai/prompt/{encoded_prompt}",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=512&height=512"
    ]

    for attempt in range(max_retries):
        for endpoint in endpoints:
            try:
                print(f"Попытка {attempt + 1}: {endpoint[:80]}...")
                if attempt > 0:
                    time.sleep(random.uniform(2, 5))
                response = requests.get(endpoint, timeout=30)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        print("✅ Изображение успешно получено")
                        return endpoint
                    else:
                        print(f"⚠️ Неожиданный тип: {content_type}")
                else:
                    print(f"❌ Ошибка {response.status_code}")
            except requests.exceptions.Timeout:
                print("⏰ Таймаут")
            except requests.exceptions.RequestException as e:
                print(f"🔴 Сетевая ошибка: {e}")
            except Exception as e:
                print(f"💥 Неожиданная ошибка: {e}")
        if attempt < max_retries - 1:
            wait = (attempt + 1) * 5
            print(f"⏳ Ждём {wait} сек")
            time.sleep(wait)
    print("❌ Все попытки исчерпаны")
    return None

# 4. Fallback на Craiyon и основная логика
def generate_fallback_image(situation, answer):
    visual_prompt = refine_visual_prompt(situation, answer)
    try:
        url = "https://api.craiyon.com/v3"
        payload = {"prompt": visual_prompt, "model": "art", "negative_prompt": ""}
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            imgs = resp.json().get("images", [])
            if imgs:
                return f"data:image/jpeg;base64,{imgs[0]}"
    except Exception as e:
        print(f"❌ Fallback ошибка: {e}")
    return None

def generate_image_with_fallback(situation, answer):
    img = generate_pollinations_image(situation, answer)
    if not img:
        print("🔄 Fallback на Craiyon")
        img = generate_fallback_image(situation, answer)
    return img

def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай шутку для ситуации: '{situation}', ответ: '{answer}'. "
        "Язык: русский, формат мема, до 2 строк."
    )
    try:
        resp = gemini_model.generate_content(prompt)
        joke = resp.text.strip() if resp and resp.text else "¯\\_(ツ)_/¯"
        print("[Gemini] Joke:", joke)
        return joke
    except Exception as e:
        print(f"Ошибка шутки: {e}")
        return "Что-то пошло не так, но это тоже смешно! 😅"

def generate_card_content(situation, answer):
    return generate_image_with_fallback(situation, answer), generate_card_joke(situation, answer)

if __name__ == "__main__":
    sit = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    ans = "Я отклоняюсь назад и говорю, что это традиция моего народа"
    img_url, joke = generate_card_content(sit, ans)
    print("Изображение:", img_url)
    print("Шутка:", joke)
