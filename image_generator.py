import requests
import google.generativeai as genai

# 1. Ключ для Gemini (Google AI Studio)
GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8" # <-- вставь свой
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")  # Для текстовой генерации (шутка)

# 2. Генерация картинки через Pollinations (простой REST API)
def generate_pollinations_image(situation, answer):
    # Промпт без юмора и текста!
    prompt = f"Digital board game card for situation: '{situation}'. Answer: '{answer}'. Minimalism, Russian board game aesthetic. No text."
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        # Pollinations возвращает прокси-URL изображения
        image_url = response.url
        print("[Pollinations] Сгенерировано изображение:", image_url)
        return image_url
    else:
        print("Ошибка генерации картинки:", response.text)
        return None

# 3. Генерация шутки через Gemini (Google AI Studio, SDK)
def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай короткую смешную фразу/шутку для настольной игры на основе ситуации: '{situation}', "
        f"и ответа игрока: '{answer}'. Язык: русский. Без мемов или сленга."
    )
    response = model.generate_content(prompt)
    print("[Gemini] Шутка для карточки:", response.text)
    return response.text

# 4. Пример вызова функций:
if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"

    # Генерация изображения (Pollinations):
    img_url = generate_pollinations_image(situation, answer)

    # Генерация шутки (Gemini):
    joke = generate_card_joke(situation, answer)

    # Можно дальше использовать img_url и joke для отправки игроку, сохранения в БД и т.д.
