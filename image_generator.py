import requests
import base64

GEMINI_API_KEY = "AIzaSyB8Bnk0wR1aKA4tNSjhdtzGJZQ6gmlGGB8"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent?key={GEMINI_API_KEY}"

def generate_card_image(situation, answer):
    prompt = (
        f"Сгенерируй digital board game card изображение для ситуации: '{situation}'. "
        f"Ответ: '{answer}'. Стиль: русская настольная игра, минимализм, юмор, Russian language."
    )
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(GEMINI_URL, headers=headers, json=data)
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

# Пример вызова:
generate_card_image(
    "Вас на свадьбе заставляют танцевать макарену перед всеми гостями",
    "Я отклоняюсь назад и говорю, что это традиция моего народа"
)
