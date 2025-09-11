# game_utils.py - НОВАЯ, РАБОЧАЯ ВЕРСИЯ БЕЗ БИБЛИОТЕК

import json
import random
from typing import Optional
from io import BytesIO

# +++ ДОБАВЛЕНЫ НУЖНЫЕ ИМПОРТЫ +++
import asyncio
import aiohttp
from urllib.parse import quote

# --- УДАЛЕНЫ СТАРЫЕ ИМПОРТЫ ---
# import pollinations - БОЛЬШЕ НЕ НУЖЕН

from aiogram import Bot
from aiogram.types import InputFile


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()

    def _load_situations(self) -> list:
        # Этот метод не менялся
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____."
        ]

    def get_random_situation(self) -> str:
        # Этот метод не менялся
        return random.choice(self.situations)

    # ↓↓↓ ВОТ ОСНОВНЫЕ ИЗМЕНЕНИЯ ↓↓↓
    async def generate_image_from_prompt(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через URL-запрос к Pollinations.ai и возвращает байты.
        """
        # Кодируем промпт для безопасной вставки в URL
        encoded_prompt = quote(prompt)
        # Формируем URL для генерации
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024"
        
        print(f"🤖 Запрашиваю изображение по URL: {image_url}")

        try:
            # Используем aiohttp для асинхронного скачивания картинки
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        # Читаем байты изображения
                        image_bytes = await resp.read()
                        print("✅ Изображение успешно получено.")
                        # Возвращаем байты в объекте BytesIO, чтобы aiogram мог их отправить
                        return BytesIO(image_bytes)
                    else:
                        print(f"❌ Ошибка от сервера Pollinations: статус {resp.status}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при скачивании изображения: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        # Этот метод почти не изменился
        if answer:
            prompt = f"{situation}. {answer}. Мультяшная яркая иллюстрация."
        else:
            prompt = f"{situation}. Мультяшная яркая иллюстрация."

        image_bytes_io = await self.generate_image_from_prompt(prompt)

        if image_bytes_io:
            await bot.send_photo(chat_id, photo=InputFile(image_bytes_io))
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False

# Глобальные экземпляры остались без изменений
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

