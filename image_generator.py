import requests
import google.generativeai as genai

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"  # <-- Убедись, что он не скомпрометирован!
genai.configure(api_key=GEMINI_API_KEY)

# Для текстовой генерации — актуальная быстрая модель Gemini 2.5 Flash Lite:
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

# 2. Генерация картинки через Pollinations (REST API, бесплатно)
def generate_pollinations_image(situation, answer):
    prompt = (
        f"Digital board game card illustration for situation: '{situation}'. "
        f"Answer: '{answer}'. Minimalism, Russian board game style, only image, no text."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.url
    else:
        print("Ошибка генерации картинки:", response.text)
        return None

# 3. Генерация шутки (текст) через Gemini Flash Lite
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую яркую шутку для карточной настольной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Формат — как мем, с иронией и игровым юмором. До 2 строк."
    )
    response = gemini_model.generate_content(prompt)
    print("[Gemini] Joke:", response.text)
    return response.text

# 4. Основная функция для интеграции (одним вызовом)
def generate_card_content(situation, answer):
    image_url = generate_pollinations_image(situation, answer)
    joke_text = generate_card_joke(situation, answer)
    return image_url, joke_text

# 5. Пример для запуска отдельно:
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    image_url, joke = generate_card_content(situation, answer)
    print("Ссылка на изображение:", image_url)
    print("Шутка для карточки:", joke)

    # Для бота:
    # await message.answer_photo(image_url, caption=joke)
