import random
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

import openai
import os

# Если используете .env, раскомментируйте строку ниже:
# from dotenv import load_dotenv; load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

# Пути
BASE_DIR = Path(__file__).parent
FONT_PATH = BASE_DIR / "arial.ttf"  # замени на любой красивый шрифт

# 🎨 Палитры (фон + акценты)
PALETTES = [
    ((30, 30, 30), (255, 20, 147)),   # чёрный фон + розовый неон
    ((20, 20, 40), (0, 255, 200)),    # тёмно-синий фон + бирюза
    ((255, 240, 200), (255, 80, 80)), # пастель + красный
    ((240, 240, 240), (0, 0, 0)),     # белый фон + чёрный текст
]

# 🎭 Эмодзи для украшения
EMOJIS = ["😂", "🔥", "🎭", "🍷", "👑", "💥", "🤯", "✨"]

def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    """
    Генерация красочной карточки для игры средствами Pillow.
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 🎨 Выбираем случайную палитру
        bg_color, accent_color = random.choice(PALETTES)

        # Создаём фон
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

        # Обёртка текста
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

        # Украшаем рамкой
        draw.rectangle([20, 20, 1004, 1004], outline=accent_color, width=10)

        # Сохраняем
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации карточки: {e}")
        return None

def generate_image_openai(situation: str, answer: str, save_path: Optional[Path] = None, size: str = "1024x1024") -> Optional[str]:
    """
    Генерация картинки через OpenAI с описанием ситуации/ответа.
    Возвращает URL картинки либо путь к файлу, если скачано.
    """
    prompt = f"Ситуация: {situation}. Ответ: {answer}. Стиль карточной игры, иллюстрировано."
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size=size
        )
        image_url = response['data'][0]['url']
        if save_path:
            import requests
            img_data = requests.get(image_url).content
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as handler:
                handler.write(img_data)
            return str(save_path)
        return image_url
    except Exception as e:
        print(f"Ошибка генерации через OpenAI: {e}")
        return None
