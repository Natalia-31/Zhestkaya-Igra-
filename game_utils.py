# game_utils.py - ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ v2

import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

# --- ↓↓↓ ВОТ ИСПРАВЛЕНИЕ ↓↓↓ ---
from aiogram import Bot
# --- ↑↑↑ КОНЕЦ ИСПРАВЛЕНИЯ ↑↑↑ ---

from aiogram.types import BufferedInputFile
from googletrans import Translator

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        self.translator = Translator()

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
        
        print(f"🤖 Запрашиваю изображение по URL: {image_url}")

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
        if answer:
            russian_subject = situation.replace("____", answer)
            try:
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(None, self.translator.translate, russian_subject, "en")
                english_subject = translated.text
            except Exception as e:
                print(f"❌ Ошибка перевода: {e}. Используем русский текст.")
                english_subject = russian_subject

            style_keywords = "A photorealistic, 8k resolution, cinematic photo of"
            prompt = f"{style_keywords} {english_subject}"
        else:
            prompt = f"A photorealistic photo of {situation}"

        image_bytes_io = await self.generate_image_from_prompt(prompt)

        if image_bytes_io:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
                caption=f"Промпт: {prompt}"
            )
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False

# Глобальные экземпляры
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
