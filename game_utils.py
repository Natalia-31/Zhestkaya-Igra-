# game_utils.py - ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ

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
        """
        Загружает ситуации из JSON-файла.
        """
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        # Резервный список на случай, если файл не найден или пуст
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____."
        ]

    def get_random_situation(self) -> str:
        """
        Возвращает случайную ситуацию из списка.
        """
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через URL-запрос к Pollinations.ai.
        """
        encoded_prompt = quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024"
        
        print(f"🤖 Запрашиваю изображение по URL: {image_url}")

        try:
            # Асинхронно скачиваем изображение
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
        """
        Собирает промпт из ситуации и ответа, генерирует и отправляет изображение.
        """
        if answer:
            # Создаем основной сюжет, заменяя прочерк ответом игрока
            main_subject = situation.replace("____", answer)
            
            # Ключевые слова для фотореализма
            style_keywords = "photorealistic, 8k resolution, cinematic lighting, highly detailed, professional photography, dslr, sharp focus"
            
            prompt = f"{main_subject}, {style_keywords}"
        else:
            # Резервный вариант, если ответа нет
            prompt = f"{situation}, photorealistic"

        # Получаем сгенерированное изображение в виде байтов
        image_bytes_io = await self.generate_image_from_prompt(prompt)

        if image_bytes_io:
            # Отправляем фото в чат
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
                caption=f"Промпт: {prompt}" # Подпись для отладки
            )
            return True

        # Если что-то пошло не так, отправляем сообщение об ошибке
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False

# Глобальный экземпляр класса, который используется в других файлах
gen = GameImageGenerator()

# Вспомогательная функция, чтобы другие файлы могли легко получить ситуацию
def get_random_situation() -> str:
    return gen.get_random_situation()
