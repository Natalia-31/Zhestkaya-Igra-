# game_utils.py - ФИНАЛЬНАЯ ВЕРСИЯ С УЛУЧШЕННЫМ ПРОМПТОМ

import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from aiogram import Bot
from aiogram.types import BufferedInputFile


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()

    def _load_situations(self) -> list:
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
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str) -> Optional[BytesIO]:
        encoded_prompt = quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024"
        
        print(f"🤖 Запраширую изображение по URL: {image_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        print("✅ Изображение успешно получено.")
                        return BytesIO(image_bytes)
                    else:
                        print(f"❌ Ошибка от сервера Pollinations: статус {resp.status}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при скачивании изображения: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        
        # --- ↓↓↓ ВОТ ВАШ ВЫБОР - ВАРИАНТ №3 ↓↓↓ ---
        if answer:
            # Формируем русскую основу
            russian_prompt = f"{situation} {answer}"
            # Добавляем английские "усилители" стиля
            style_enhancers = "cinematic, vibrant colors, fun, cartoon, high detail, masterpiece, sharp focus"
            prompt = f"{russian_prompt}, {style_enhancers}"
        else:
            # Резервный вариант, если ответа нет
            prompt = f"{situation}, {style_enhancers}"
        # --- ↑↑↑ КОНЕЦ ИЗМЕНЕНИЙ ПРОМПТА ↑↑↑ ---

        image_bytes_io = await self.generate_image_from_prompt(prompt)

        if image_bytes_io:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
                caption=f"Промпт: {prompt}" # Добавил вывод промпта в подпись для удобства отладки
            )
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False

# Глобальные экземпляры
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

