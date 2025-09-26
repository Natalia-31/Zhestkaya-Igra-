import requests
import google.generativeai as genai

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"  # <-- Вставьте свой API-ключ из Google AI Studio
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-pro")  # Для текстовой генерации (шутка)

# 2. Генерация картинки через Pollinations (REST API, без регистрации/ключа)
def generate_pollinations_image(situation, answer):
    # Промпт без текста, минимализм
    prompt = (
        f"Digital board game card illustration for situation: '{situation}'. "
        f"Answer: '{answer}'. Minimalism, Russian board game style, only image, no text."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        image_url = response.url  # Прямой URL на сгенерированную картинку
        print("[Pollinations] Image URL:", image_url)
        return image_url
    else:
        print("Ошибка генерации картинки:", response.text)
        return None

# 3. Генерация шутки (текст) через Gemini Pro
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую смешную фразу/шутку для настольной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Без мемов, только остроумно."
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

    # Пример: для aiogram-бота:
    # await message.answer_photo(image_url, caption=joke)
