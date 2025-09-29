import requests
import google.generativeai as genai

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "ВАШ_КЛЮЧ"  # ⚠️ Вынеси в .env для безопасности!
genai.configure(api_key=GEMINI_API_KEY)

# Для текстовой генерации (шутки)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")


# 2. Генерация картинки через Pollinations
def generate_pollinations_image(situation, answer):
    # Средний, более осмысленный промпт (без лишних наворотов)
    prompt = (
        f"Cartoon style illustration for a funny Russian board game card. "
        f"Scene: {situation}. "
        f"Player action: {answer}. "
        f"Minimalism, humor, bold lines, no text."
    )

    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    response = requests.get(url, params=params)

    if response.status_code == 200:
        return response.url
    else:
        print("Ошибка генерации картинки:", response.text)
        return None


# 3. Генерация шутки (оставил как у тебя)
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую яркую шутку для карточной настольной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Формат — как мем, с иронией и игровым юмором. До 2 строк."
    )
    response = gemini_model.generate_content(prompt)
    print("[Gemini] Joke:", response.text)
    return response.text


# 4. Основная функция
def generate_card_content(situation, answer):
    image_url = generate_pollinations_image(situation, answer)
    joke_text = generate_card_joke(situation, answer)
    return image_url, joke_text


# 5. Пример запуска отдельно
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    image_url, joke = generate_card_content(situation, answer)
    print("Ссылка на изображение:", image_url)
    print("Шутка для карточки:", joke)

    # Для бота (aiogram):
    # await message.answer_photo(image_url, caption=joke)
