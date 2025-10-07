# game_utils/decks.py
import os
import json
import random
from pathlib import Path
from typing import List, Optional, Tuple
import asyncio
import aiohttp
from dotenv import load_dotenv
import google.generativeai as genai
from gigachat_utils import gigachat_generator  # НОВОЕ: импорт GigaChat

# ====== Загрузка ключей ======
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Модель Gemini для текста (шутки)
gemini_text_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

# ====== Менеджер колод ======
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json", base: Path | None = None):
        self.base_dir = base or Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str]    = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        for enc in ("utf-8-sig", "utf-8"):
            try:
                data = json.loads(file_path.read_text(encoding=enc))
                if isinstance(data, list):
                    seen, out = set(), []
                    for x in data:
                        if isinstance(x, str):
                            x = x.strip()
                            if x and x not in seen:
                                seen.add(x)
                                out.append(x)
                    return out
                return []
            except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
                continue
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Тестовая ситуация"

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = list(self.answers)
        random.shuffle(deck)
        return deck

# ====== Генерация изображений ======

async def generate_gigachat_image(situation: str, answer: str) -> Optional[str]:
    """
    Генерирует изображение через GigaChat + Kandinsky 3.1
    
    Returns:
        Путь к локальному файлу или None
    """
    try:
        print(f"🎨 Генерация через GigaChat + Kandinsky 3.1...")
        
        # Промпт для мема на русском
        prompt = (
            f"Создай забавную иллюстрацию-мем для карточной игры. "
            f"Ситуация: '{situation}'. Ответ игрока: '{answer}'. "
            f"Стиль: яркие цвета, минимализм, юмор, мемный стиль. "
            f"БЕЗ текста на изображении!"
        )
        
        # Вызываем GigaChat синхронно в отдельном потоке
        image_path = await asyncio.to_thread(
            gigachat_generator.generate_image,
            prompt
        )
        
        if image_path:
            print(f"✅ GigaChat успешно сгенерировал изображение")
            return image_path
        else:
            print("⚠️ GigaChat не вернул изображение")
            return None
        
    except Exception as e:
        print(f"❌ Ошибка GigaChat Image: {e}")
        return None

async def generate_pollinations_image(situation: str, answer: str) -> Optional[str]:
    """
    Генерация через Pollinations.ai (запасной вариант)
    """
    prompt = (
        f"Cartoon style card for a Russian Telegram game 'Жесткая игра': Situation: {situation}, "
        f"Player's answer: {answer}. Minimalism, humor, bold lines, no text overlay on the image itself."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=20) as resp:
                if resp.status == 200:
                    print(f"✅ Pollinations вернул изображение")
                    return str(resp.url)
    except Exception as e:
        print(f"⚠️ Pollinations error: {e}")
    return None

# ====== Генерация шутки через Gemini ======

async def generate_card_joke(situation: str, answer: str) -> str:
    """
    Генерирует саркастическую шутку через Gemini
    """
    if not gemini_text_model:
        return f"Ситуация: {situation} | Ответ: {answer}"
    
    prompt = (
        f"Придумай короткую смешную подпись для настольной игры.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Формат: саркастический мем, максимум 2 строки, на русском."
    )
    try:
        response = await asyncio.to_thread(gemini_text_model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Ошибка генерации шутки: {e}")
        return "😅 Не удалось сгенерировать шутку."

# ====== Основная функция генерации контента ======

async def generate_card_content(situation: str, answer: str) -> Tuple[Optional[str], str]:
    """
    Генерирует изображение и шутку для выигрышной комбинации
    
    Приоритет генерации:
    1. GigaChat + Kandinsky 3.1 (лучшее качество, русский язык) ✅
    2. Pollinations.ai (запасной вариант)
    
    Returns:
        (image_path_or_url, joke_text)
    """
    # Генерируем шутку параллельно
    joke_task = asyncio.create_task(generate_card_joke(situation, answer))
    
    # 1. Пробуем GigaChat + Kandinsky (ПРИОРИТЕТ - лучшее качество)
    image_result = await generate_gigachat_image(situation, answer)
    
    if not image_result:
        # 2. Запасной вариант - Pollinations
        print("🔄 Переключаемся на Pollinations...")
        image_result = await generate_pollinations_image(situation, answer)
    
    # Ждем шутку
    joke_text = await joke_task
    
    return image_result, joke_text

# ====== Инициализация менеджера колод ======
decks = DeckManager(base=Path(__file__).resolve().parent)
