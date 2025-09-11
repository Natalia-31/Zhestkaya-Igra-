# ИСПРАВЛЕННАЯ ВЕРСИЯ С POLLINATIONS.AI

import json
import random
import asyncio
from pathlib import Path
from typing import Optional
from io import BytesIO

# --- УДАЛЕНЫ импорты OpenAI и связанные с ним ---
# import aiohttp, aiofiles, os
# from openai import AsyncOpenAI
# from aiogram.types import FSInputFile

# +++ ДОБАВЛЕНЫ импорты для Pollinations и работы с памятью +++
import pollinations
from aiogram.types import InputFile
from aiogram import Bot


# --- КЛАСС ПЕРЕПИСАН ДЛЯ РАБОТЫ С POLLINATIONS ---

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        # Убрали images_dir, так как сохранять файлы больше не нужно
        self.situations_file = situations_file
        self.situations = self._load_situations()
        # Инициализируем модель pollinations один раз при создании объекта
        self.image_model = pollinations.Image(width=1024, height=1024)

    def _load_situations(self) -> list:
        # Этот метод остался без изменений
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
        # Этот метод остался без изменений
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через Pollinations.ai и возвращает его в виде байтового объекта в памяти.
        """
        print(f"🤖 Pollinations: Начинаю генерацию для промпта: '{prompt}'")
        try:
            # Запускаем синхронную библиотеку в асинхронном коде без блокировки
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(None, self.image_model, prompt)

            # Сохраняем изображение в оперативную память
            bio = BytesIO()
            bio.name = 'image.jpeg'
            image.save(bio, 'JPEG')
            bio.seek(0)
            print("✅ Pollinations: Изображение успешно сгенерировано в память.")
            return bio

        except Exception as e:
            print(f"❌ Pollinations: Ошибка при генерации изображения: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        # Этот метод остался почти без изменений, только промпт и способ отправки
        if answer:
            prompt = f"Ситуация: {situation}. Ответ игрока: {answer}. Мультяшная яркая иллюстрация в стиле мемов."
        else:
            prompt = f"Ситуация: {situation}. Мультяшная яркая иллюстрация в стиле мемов."

        # Вызываем новый метод генерации
        image_bytes = await self.generate_image_from_prompt(prompt)

        if image_bytes:
            # Отправляем фото из памяти (InputFile), а не с диска (FSInputFile)
            await bot.send_photo(chat_id, photo=InputFile(image_bytes))
            return True

        # Отправляем сообщение об ошибке, если генерация не удалась
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False


# --- ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ ОСТАЛИСЬ БЕЗ ИЗМЕНЕНИЙ ---

# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
