import requests
import google.generativeai as genai
import os

# 1. Ключ Gemini (Google AI Studio)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Не найден GEMINI_API_KEY в окружении")

genai.configure(api_key=GEMINI_API_KEY)

# Для текстовой генерации — быстрая модель Gemini
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")


# 2. Генерация краткого описания сцены через Gemini
def generate_scene_prompt(situation, answer):
    prompt = (
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Сделай короткое (1-2 предложения) описание визуальной сцены для генерации картинки. "
        "Стиль: абсурдный, ироничный, как для настольной карточной игры. "
        "Не используй имена, бренды и текст в картинке."
    )
    response = gemini_model.generate_content(prompt)
    return response.text.strip()


# 3. Генерация картинки через Pollinations
def generate_pollinations_image(scene_description):
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": scene_description}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.url
    else:
        print("Ошибка генерации картинки:", response.text)
        return None


# 4. Генерация шутки (текст) через Gemini
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую смешную шутку для карточной игры.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Формат: ироничная подпись как мем, максимум 2 строки, на русском."
    )
    response = gemini_model.generate_content(prompt)
    return response.text.strip()


# 5. Основная функция
def generate_card_content(situation, answer):
    scene_description = generate_scene_prompt(situation, answer)
    image_url = generate_pollinations_image(scene_description)
    joke_text = generate_card_joke(situation, answer)
    return image_url, joke_text


# 6. Пример запуска
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    image_url, joke = generate_card_content(situation, answer)
    print("Ссылка на изображение:", image_url)
    print("Шутка для карточки:", joke)
