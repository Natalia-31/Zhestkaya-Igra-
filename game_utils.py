# game_utils.py
import os
import json
import random
from pathlib import Path
from typing import List, Optional, Tuple
import asyncio
import aiohttp
from dotenv import load_dotenv
import google.generativeai as genai
from gigachat_utils import gigachat_generator

# ====== Загрузка ключей ======
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API настроен")
else:
    print("⚠️ GEMINI_API_KEY не найден")

# Модель Gemini - ИСПРАВЛЕНО для работы с текущей версией API
try:
    # Попробуем несколько вариантов моделей
    model_names = [
        "gemini-pro",  # Старая стабильная модель
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "models/gemini-pro",
    ]
    
    gemini_text_model = None
    for model_name in model_names:
        try:
            gemini_text_model = genai.GenerativeModel(model_name)
            # Пробуем сгенерировать тестовый запрос
            test_response = gemini_text_model.generate_content("test")
            print(f"✅ Модель {model_name} инициализирована успешно")
            break
        except Exception as e:
            print(f"⚠️ Модель {model_name} недоступна: {e}")
            continue
    
    if not gemini_text_model:
        print("❌ Ни одна модель Gemini не доступна")
        
except Exception as e:
    print(f"❌ Ошибка инициализации Gemini: {e}")
    gemini_text_model = None

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
    
    def get_all_situations(self) -> List[str]:
        return list(self.situations)
    
    def get_random_from_list(self, situations_list: List[str]) -> str:
        return random.choice(situations_list) if situations_list else "Тестовая ситуация"

# ====== Генерация изображений ======

async def generate_gigachat_image(situation: str, answer: str) -> Optional[str]:
    """Генерирует изображение через GigaChat + Kandinsky 3.1"""
    try:
        print(f"🎨 Генерация через GigaChat + Kandinsky 3.1...")
        
        prompt = (
            f"Создай яркую комичную иллюстрацию. "
            f"Игровая ситуация: '{situation}'. "
            f"Ответ игрока: '{answer}'. "
            f"Визуальный стиль: современный мем-арт, сочные насыщенные цвета, "
            f"забавные персонажи, выразительные эмоции, абсурдный юмор. "
            f"Композиция: динамичная, с четким фокусом на главном действии. "
            f"КРИТИЧНО: БЕЗ текста и подписей на изображении!"
        )
        
        image_path = await asyncio.to_thread(
            gigachat_generator.generate_image,
            prompt
        )
        
        if image_path:
            print(f"✅ GigaChat успешно сгенерировал изображение: {image_path}")
            return image_path
        else:
            print("⚠️ GigaChat не вернул изображение")
            return None
        
    except Exception as e:
        print(f"❌ Ошибка GigaChat: {e}")
        return None

async def generate_pollinations_image(situation: str, answer: str) -> Optional[str]:
    """Генерация через Pollinations.ai (запасной вариант)"""
    prompt = (
        f"Cartoon style card for a Russian Telegram game: Situation: {situation}, "
        f"Player answer: {answer}. Minimalism, humor, bold lines, no text."
    )
    url = f"https://image.pollinations.ai/prompt/{prompt}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status == 200:
                    print(f"✅ Pollinations вернул изображение")
                    return str(resp.url)
    except Exception as e:
        print(f"⚠️ Pollinations error: {e}")
    return None

async def generate_card_joke(situation: str, answer: str) -> str:
    """Генерирует шутку через Gemini"""
    
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY не задан")
        return f"Ситуация: {situation} | Ответ: {answer} 😄"
    
    if not gemini_text_model:
        print("⚠️ Модель Gemini не инициализирована")
        return f"Отличный выбор! '{answer}' - именно то, что нужно! 😄"
    
    prompt = (
        f"Придумай короткую смешную подпись для настольной игры.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        f"Формат: саркастический мем, максимум 2 строки, на русском."
    )
    
    try:
        print(f"🤖 Генерирую шутку через Gemini...")
        response = await asyncio.to_thread(gemini_text_model.generate_content, prompt)
        joke = response.text.strip()
        print(f"✅ Шутка сгенерирована: {joke[:60]}...")
        return joke
    except Exception as e:
        print(f"❌ Ошибка генерации шутки: {e}")
        # Запасной вариант - простая шутка
        return f"'{answer}' - гениально! Именно это я и хотел услышать! 🎉"

async def generate_card_content(situation: str, answer: str) -> Tuple[Optional[str], str]:
    """Генерирует изображение и шутку"""
    print(f"📝 Генерация контента для: '{situation}' + '{answer}'")
    
    # Генерируем шутку параллельно
    joke_task = asyncio.create_task(generate_card_joke(situation, answer))
    
    # 1. Пробуем GigaChat
    image_result = await generate_gigachat_image(situation, answer)
    
    if not image_result:
        # 2. Запасной вариант
        print("🔄 Переключаемся на Pollinations...")
        image_result = await generate_pollinations_image(situation, answer)
    
    joke_text = await joke_task
    
    print(f"📦 Результат: image={bool(image_result)}, joke={joke_text[:50]}...")
    
    return image_result, joke_text

# Инициализация менеджера колод
decks = DeckManager(base=Path(__file__).resolve().parent)
