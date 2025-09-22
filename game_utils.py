import os
from io import BytesIO
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile
import openai

# Загрузка переменных окружения
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан в .env")

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

# ---------- Вспомогательные функции ----------
def create_prompt(situation: str, answer: str) -> str:
    """Формируем текстовый промпт для генерации изображения."""
    # Очистка и экранирование ситуации и ответа при необходимости
    sit = situation.strip().replace("\n", " ")
    ans = answer.strip().replace("\n", " ")
    return f"Illustration for card game scene: \"{sit}\"; player’s answer: \"{ans}\"; vibrant colors, cartoon style, simple shapes"

# ---------- Генератор изображений ----------
class GameImageGenerator:
    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        """Попытка сгенерировать картинку через Pollinations API."""
        url = f"https://image.pollinations.ai/prompt/{aiohttp.helpers.quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=20) as resp:
                    if resp.status == 200:
                        return BytesIO(await resp.read())
        except Exception:
            return None
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        """Попытка сгенерировать картинку через NanoBanana API."""
        if not NANO_API_KEY:
            return None
        api_url = "https://api.nanobanana.ai/v1/generate"
        payload = {"prompt": prompt, "size": "512x512"}
        headers = {"Authorization": f"Bearer {NANO_API_KEY}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    img_url = data.get("image_url") or data.get("url")
                if not img_url:
                    return None
                async with aiohttp.ClientSession() as session:
                    async with session.get(img_url, timeout=60) as img_resp:
                        if img_resp.status == 200:
                            return BytesIO(await img_resp.read())
        except Exception:
            return None
        return None

    async def send_illustration(
        self,
        bot: Bot,
        chat_id: int,
        situation: str,
        answer: Optional[str] = None
    ) -> bool:
        """Отправка иллюстрации для ситуации и ответа."""
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False

        prompt = create_prompt(situation, answer)

        img_stream: Optional[BytesIO] = None

        # Попытка через OpenAI Image API
        try:
            img_resp = await openai.Image.acreate(
                prompt=prompt,
                n=1,
                size="512x512"
            )
            img_url = img_resp.data[0].url
            async with aiohttp.ClientSession() as session:
                async with session.get(img_url, timeout=30) as resp:
                    if resp.status == 200:
                        img_stream = BytesIO(await resp.read())
        except Exception:
            img_stream = None

        # Фолбэк на другие сервисы
        if not img_stream:
            img_stream = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)

        if not img_stream:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
            return False

        img_stream.seek(0)
        await bot.send_photo(
            chat_id,
            photo=BufferedInputFile(img_stream.read(), filename="illustration.png")
        )
        return True

# Экземпляр генератора изображений
image_gen = GameImageGenerator()
