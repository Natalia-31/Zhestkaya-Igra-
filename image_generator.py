import requests
import google.generativeai as genai
import urllib.parse

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "ВАШ_КЛЮЧ"  # ⚠️ Вынеси в .env для безопасности!
genai.configure(api_key=GEMINI_API_KEY)

# Модель Gemini для текста
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")


# 2. Генерация уточнённого визуального промпта через Gemini
def refine_visual_prompt(situation, answer):
    prompt = (
        f"Ситуация: {situation}. Ответ игрока: {answer}. "
        f"Составь короткое описание сцены на английском языке для генерации картинки. "
        f"Фокус: персонаж, действие, атмосфера. Стиль: cartoon, board game art, minimalism. "
        f"Выведи только описание сцены, максимум 15 слов."
    )
    response = gemini_model.generate_content(prompt)
    text = response.text.strip() if response and response.text else ""

    # fallback, если Gemini вернул что-то пустое или слишком длинное
    if not text or len(text) > 200:
        text = f"Funny cartoon illustration, {situation}, {answer}, board game style"

    return text


# 3. Генерация картинки через Pollinations (REST API)
def generate_pollinations_image(situation, answer):
    visual_prompt = refine_visual_prompt(situation, answer)
    print("[Visual prompt]:", visual_prompt)  # для отладки

    # Кодируем промпт для URL
    encoded_prompt = urllib.parse.quote(visual_prompt)

    # Pollinations endpoint
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    return url


# 4. Генерация шутки через Gemini
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую яркую шутку для карточной настольной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Формат — как мем, с иронией и игровым юмором. До 2 строк."
    )
    response = gemini_model.generate_content(prompt)
    joke = response.text.strip() if response and response.text else "¯\\_(ツ)_/¯"
    print("[Gemini joke]:", joke)
    return joke


# 5. Основная функция
def generate_card_content(situation, answer):
    image_url = generate_pollinations_image(situation, answer)
    joke_text = generate_card_joke(situation, answer)
    return image_url, joke_text


# 6. Пример запуска отдельно
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    image_url, joke = generate_card_content(situation, answer)
    print("Ссылка на изображение:", image_url)
    print("Шутка для карточки:", joke)

    # Для бота (aiogram):
    # await message.answer_photo(image_url, caption=joke)
