import random
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
import requests
import base64
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "твой_ключ"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"
BASE_DIR = Path(__file__).parent
FONT_PATH = BASE_DIR / "arial.ttf"
GENERATED_DIR = BASE_DIR / "generated_images"
GENERATED_DIR.mkdir(exist_ok=True)

def wrap(text: str, width: int = 25):
    words, lines, buf = text.split(), [], []
    for w in words:
        buf.append(w)
        if len(" ".join(buf)) > width:
            lines.append(" ".join(buf[:-1]))
            buf = [w]
    if buf:
        lines.append(" ".join(buf))
    return lines

def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg_color, accent_color = (30, 30, 30), (255, 20, 147)
        img = Image.new("RGB", (1024, 1024), color=bg_color)
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype(str(FONT_PATH), 60)
            font_body = ImageFont.truetype(str(FONT_PATH), 42)
        except IOError:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
        title_text = "Жесткая Игра"
        draw.text((40, 40), title_text, fill=accent_color, font=font_title)
        y = 180
        draw.text((40, y), "🎭 Ситуация:", fill=accent_color, font=font_body)
        y += 60
        for line in wrap(situation):
            draw.text((60, y), line, fill=(255, 255, 255), font=font_body)
            y += 50
        y += 40
        draw.text((40, y), "👉 Ответ:", fill=accent_color, font=font_body)
        y += 60
        for line in wrap(answer):
            draw.text((60, y), line, fill=(255, 255, 255), font=font_body)
            y += 50
        draw.rectangle([20, 20, 1004, 1004], outline=accent_color, width=10)
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации карточки: {e}")
        return None

def generate_image_via_gemini(situation: str, answer: str) -> Optional[bytes]:
    prompt = (
        f"Сгенерируй digital board game card изображение для ситуации: '{situation}'. "
        f"Ответ: '{answer}'. Стиль: русская настольная игра, минимализм, юмор, Russian language."
    )
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        r = requests.post(GEMINI_URL, headers=headers, json=data)
        r.raise_for_status()
        response_json = r.json()
        print("Gemini response:", repr(response_json))  # <-- ВЫВОДИТЬ ВСЕГДА!
        parts = (
            response_json.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        for part in parts:
            if "inlineData" in part and "data" in part["inlineData"]:
                img_b64 = part["inlineData"]["data"]
                return base64.b64decode(img_b64)
        print("Картинка не найдена в ответе Gemini.")
        return None
    except Exception as e:
        print("EXCEPT!", repr(e))
        if hasattr(e, 'response') and e.response is not None:
            print("Ответ Gemini:", e.response.text)
        return None

def create_card(situation: str, answer: str, use_gemini: bool = True) -> Optional[Path]:
    filename = f"{random.randint(0,999999)}.png"
    out_path = GENERATED_DIR / filename
    if use_gemini:
        img_bytes = generate_image_via_gemini(situation, answer)
        if img_bytes:
            out_path.write_bytes(img_bytes)
            print(f"Карточка сохранена: {out_path}")
            return out_path
        print("Не удалось получить картинку от Gemini! Генерируем локально...")
    return generate_image_file(situation, answer, out_path)

if __name__ == "__main__":
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"
    card_path = create_card(situation, answer, use_gemini=True)
    if card_path:
        print(f"Карточка сохранена: {card_path}")
    else:
        print("Ошибка генерации карточки.")
