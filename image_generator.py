import random
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
import requests
import base64
import os

# Пути
BASE_DIR = Path(__file__).parent
FONT_PATH = BASE_DIR / "arial.ttf"  # замените на свой шрифт
GENERATED_DIR = BASE_DIR / "generated_images"
GENERATED_DIR.mkdir(exist_ok=True)

# 🎨 Палитры (фон + акценты)
PALETTES = [
    ((30, 30, 30), (255, 20, 147)),   # чёрный фон + розовый неон
    ((20, 20, 40), (0, 255, 200)),    # тёмно-синий фон + бирюза
    ((255, 240, 200), (255, 80, 80)), # пастель + красный
    ((240, 240, 240), (0, 0, 0)),     # белый фон + чёрный текст
]

# 🎭 Эмодзи для украшения
EMOJIS = ["😂", "🔥", "🎭", "🍷", "👑", "💥", "🤯", "✨"]

# ➡️ Gemini (Google) API настройки
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "ВАШ_API_КЛЮЧ"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"

def wrap(text: str, width: int = 25) -> list[str]:
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
    # стандартная генерация Pillow, без изменений
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg_color, accent_color = random.choice(PALETTES)
        img = Image.new("RGB", (1024, 1024), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Шрифты
        try:
            font_title = ImageFont.truetype(str(FONT_PATH), 60)
            font_body = ImageFont.truetype(str(FONT_PATH), 42)
        except IOError:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        # Заголовок
        title_text = f"Жесткая Игра {random.choice(EMOJIS)}"
        draw.text((40, 40), title_text, fill=accent_color, font=font_title)

        # Ситуация
        y = 160
        draw.text((40, y), "🎭 Ситуация:", fill=accent_color, font=font_body)
        y += 60
        for line in wrap(situation):
            draw.text((60, y), line, fill=(255, 255, 255), font=font_body)
            y += 50

        # Ответ
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

def generate_image_via_gemini(prompt: str) -> Optional[bytes]:
    """
    Генерация изображения через Gemini API (Google’s multimodal model)
    """
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
        # Проверьте структуру ответа — может отличаться, ниже типовой паттерн
        # Распечатаем ответ для отладки:
        # print(response_json)
        parts = response_json.get("candidates", [])[0]["content"]["parts"]
        for part in parts:
            if "inlineData" in part:
                img_b64 = part["inlineData"].get("data")
                if img_b64:
                    return base64.b64decode(img_b64)
        print("Не найдено поля inlineData с base64 изображением.")
        return None
    except Exception as e:
        print(f"Ошибка Gemini генерации: {e}")
        return None

def create_card(situation: str, answer: str, use_api: bool = True) -> Optional[Path]:
    filename = f"{random.randint(0,999999)}.png"
    out_path = GENERATED_DIR / filename

    if use_api:
        # Детализированный prompt для генерации карточки
        prompt = (
            "Сгенерируй python base64 image для карточки настольной русской игры, "
            f"с заголовком 'Жесткая Игра', ситуацией: '{situation}', ответом: '{answer}'. "
            "Стиль: цветная минималистичная карточка для настольной игры, смешно, современно."
        )
        data = generate_image_via_gemini(prompt)
        if data:
            out_path.write_bytes(data)
            return out_path
        # fallback на Pillow
    return generate_image_file(situation, answer, out_path)

if __name__ == "__main__":
    # Пример использования
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"
    card_path = create_card(situation, answer, use_api=True)
    if card_path:
        print(f"Карточка сохранена: {card_path}")
    else:
        print("Не удалось создать карточку.")
