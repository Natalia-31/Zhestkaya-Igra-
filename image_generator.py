import requests
import base64

GEMINI_API_KEY = "AIzaSyD25MoSKMDlfR8G9_IEvVza_L78VRkt0RM"
# Для генерации изображения проверь актуальный endpoint своей модели!
GEMINI_IMAGE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent?key={GEMINI_API_KEY}"
GEMINI_TEXT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

def generate_card_image(situation, answer):
    # Промпт только на картинку, без мемов и юмора
    prompt = (
        f"Создай цифровую иллюстрацию для карточки настольной игры по этой ситуации: '{situation}'. "
        f"Игровой ответ: '{answer}'. Стиль: минимализм, цифровое искусство."
        f" Без текста, только картинка, российская эстетика."
    )
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(GEMINI_IMAGE_URL, headers=headers, json=data)
    r.raise_for_status()
    response_json = r.json()
    parts = (
        response_json.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    for part in parts:
        if "inlineData" in part and "data" in part["inlineData"]:
            img_b64 = part["inlineData"]["data"]
            img_bytes = base64.b64decode(img_b64)
            with open("game_card.png", "wb") as f:
                f.write(img_bytes)
            print("Изображение сохранено: game_card.png")
            return img_bytes
    print("Картинка не найдена в ответе Gemini.")
    return None


def generate_card_joke(situation, answer):
    # Промпт только на короткую смешную шутку, без мемов и излишнего юмора
    prompt = (
        f"Придумай короткую остроумную смешную фразу/шутку по настольной ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык: русский. Не используй мемы или интернет-слэнг."
    )
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(GEMINI_TEXT_URL, headers=headers, json=data)
    r.raise_for_status()
    response_json = r.json()
    parts = (
        response_json.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    for part in parts:
        if "text" in part:
            joke = part["text"]
            print("Шутка для карточки:")
            print(joke)
            return joke
    print("Шутка не найдена в ответе Gemini.")
    return None

# Пример вызова:
generate_card_image(
    "Вас на свадьбе заставляют танцевать макарену перед всеми гостями",
    "Я отклоняюсь назад и говорю, что это традиция моего народа"
)
generate_card_joke(
    "Вас на свадьбе заставляют танцевать макарену перед всеми гостями",
    "Я отклоняюсь назад и говорю, что это традиция моего народа"
)
