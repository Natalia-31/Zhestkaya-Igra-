import requests
import google.generativeai as genai
import urllib.parse

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"  # вынести в .env!
genai.configure(api_key=GEMINI_API_KEY)

# Модель Gemini
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

# 2. Генерация картинки через Pollinations
def generate_pollinations_image(situation, answer):
    prompt = (
        f"Cartoon style illustration for a funny Russian board game card. "
        f"Scene: {situation}. Player action: {answer}. "
        f"Minimalism, humor, bold lines, no text."
    )
    # URL-кодирование
    encoded = urllib.parse.quote(prompt, safe='')
    url = f"https://image.pollinations.ai/prompt/{encoded}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        # Прямой URL сгенерированного изображения
        return resp.url
    except requests.exceptions.RequestException as e:
        print("Ошибка генерации изображения:", e)
        return None

# 3. Генерация шутки через Gemini
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую яркую шутку для карточной настольной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Формат – мем, с иронией, до 2 строк."
    )
    try:
        response = gemini_model.generate_content(prompt)
        # Текст обычно в response.text
        text = response.text.strip() if response and response.text else "Шутка не получилась 🤷"
    except Exception as e:
        print("Ошибка Gemini:", e)
        text = "Шутка не сгенерировалась 🤷"
    print("[Gemini] Joke:", text)
    return text

# 4. Основная функция
def generate_card_content(situation, answer):
    image_url = generate_pollinations_image(situation, answer)
    joke = generate_card_joke(situation, answer)
    return image_url, joke

# 5. Пример запуска
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    img, joke = generate_card_content(situation, answer)
    print("Ссылка на изображение:", img)
    print("Шутка для карточки:", joke)
