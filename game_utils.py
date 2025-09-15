# game_utils.py — ситуации/ответы из JSON + ваш рабочий блок генерации изображений

import os
import json
import random
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import asyncio
import aiohttp
import base64
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# Загружаем API-ключи из файла .env
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

def create_prompt(situation: str, answer: str) -> str:
    """Создает оптимизированный английский промпт для всех сервисов."""
    combined = situation.replace("____", answer).strip().replace(".", "").replace(",", "")
    
    # Краткий словарь для быстрого перевода
    quick_translations = {
        "На вечеринке": "at a party",
        "опоздать": "being late",
        "холодильник": "refrigerator",
        "кот в сапогах": "Puss in Boots",
        "работа": "work",
        "школа": "school",
        "день рождения": "birthday",
        "талант": "talent",
        "резюме": "resume",
    }
    
    text = combined
    for ru, en in quick_translations.items():
        text = text.replace(ru, en)
        
    # Если остались русские слова, переводим через Google Translate
    if any(ord(c) > 127 for c in text):
        try:
            from googletrans import Translator
            translator = Translator()
            text = translator.translate(combined, dest='en').text
            print(f"🔄 [Перевод] {combined} -> {text}")
        except Exception as e:
            print(f"⚠️ [Ошибка перевода] {e}")
            
    # Добавляем "магические слова" для улучшения качества
    modifiers = "photorealistic, cinematic lighting, ultra detailed, 8k, trending on Artstation"
    final_prompt = f"{text}, {modifiers}"
    print(f"📝 [Финальный промпт] {final_prompt}")
    return final_prompt


class DeckManager:
    """
    Загружает situations.json и answers.json (UTF-8 и UTF-8-SIG),
    отдаёт случайную ситуацию и перемешанную колоду ответов.
    """
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()

        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        # Пытаемся прочесть как UTF-8, затем как UTF-8-SIG (BOM)
        for enc in ("utf-8", "utf-8-sig"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc}): {len(data)} из {file_path}")
                    return data
                else:
                    print(f"⚠️ {file_path} ({label}) не содержит JSON-список")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path} ({label})")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Кодировка {enc} не подошла: {e} — пробуем следующую…")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в {file_path} ({label}): {e}")
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка при чтении {file_path} ({label}): {e}")
                return []
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "На вечеринке я неожиданно ____."

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck


class GameImageGenerator:
    """
    ВАШ РАБОЧИЙ БЛОК ГЕНЕРАЦИИ — параллельно через несколько сервисов
    """
    def __init__(self):
        # Ключи и URL для всех сервисов
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"
        
        self.replicate_token = REPLICATE_API_TOKEN
        self.replicate_url = "https://api.replicate.com/v1/predictions"

    # --- Методы для каждого сервиса (ваши рабочие) ---
    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        """Самый быстрый, без ключа."""
        print("🟡 Запускаю Pollinations...")
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        print("✅ Pollinations ответил первым!")
                        return BytesIO(await resp.read())
        except Exception as e:
            print(f"⚠️ Pollinations: {e}")
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        """Требует ключ, средняя скорость."""
        if not self.nb_key: return None
        print("🔵 Запускаю Nano Banana...")
        payload = {"prompt": prompt, "model": "sdxl", "width": 512, "height": 512, "steps": 20, "cfg_scale": 7.0}
        headers = {"Authorization": f"Bearer {self.nb_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.nb_url, json=payload, headers=headers, timeout=40) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        img_url = data.get("image_url")
                        if img_url:
                            async with session.get(img_url, timeout=20) as img_resp:
                                if img_resp.status == 200:
                                    print("✅ Nano Banana ответил!")
                                    return BytesIO(await img_resp.read())
        except Exception as e:
            print(f"⚠️ Nano Banana: {e}")
        return None

    async def _try_horde(self, prompt: str) -> Optional[BytesIO]:
        """Требует ключ, может быть в очереди."""
        if not self.horde_key: return None
        print("🟣 Запускаю AI Horde...")
        # Можно добавить полную реализацию AI Horde при необходимости
        return None

    async def _try_replicate(self, prompt: str) -> Optional[BytesIO]:
        """Требует ключ, может быть медленным."""
        if not self.replicate_token: return None
        print("⚪️ Запускаю Replicate...")
        # Можно добавить полную реализацию Replicate при необходимости
        return None

    # --- Основной метод генерации (ваш рабочий) ---
    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        """
        Совместимый API для handlers: send_illustration вместо generate_and_send_image
        """
        prompt = create_prompt(situation, answer) if answer else "A photorealistic image, masterpiece, best quality"
        
        # Список задач для параллельного выполнения
        tasks = [
            self._try_pollinations(prompt),
            self._try_nanobanana(prompt),
            # self._try_horde(prompt),       # Можно раскомментировать, если есть ключ
            # self._try_replicate(prompt),  # Можно раскомментировать, если есть ключ
        ]
        
        # Запускаем все задачи и ждем первого успешного результата
        for future in asyncio.as_completed(tasks):
            try:
                result_image = await future
                if result_image:
                    # Отправляем первое полученное изображение
                    await bot.send_photo(
                        chat_id,
                        photo=BufferedInputFile(file=result_image.read(), filename="generated_image.jpeg"),
                        caption=f"Промпт: {prompt}"
                    )
                    return True # Успешно, выходим
            except Exception as e:
                print(f"Ошибка в одной из задач: {e}")
        
        # Если ни один сервис не ответил
        await bot.send_message(chat_id, "⚠️ Ни один из сервисов генерации не смог создать изображение. Попробуйте позже.")
        return False


# Экспорт для хэндлеров
decks = DeckManager()
gen = GameImageGenerator()

# Совместимость со старым API
def get_random_situation() -> str:
    return decks.get_random_situation()
