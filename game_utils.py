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
POLLO_API_KEY = os.getenv("POLLO_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан в .env")

openai.api_key = OPENAI_API_KEY


# ---------- Вспомогательные функции ----------
def create_prompt(situation: str, answer: str) -> str:
    """Формируем текстовый промпт для генерации изображения."""
    return f"Иллюстрация для ситуации: {situation}. Ответ игрока: {answer}. Сгенерируй яркое изображение."


def create_video_prompt(situation: str, answer: str) -> str:
    """Формируем промпт для генерации видео."""
    return f"Короткий видеоролик, иллюстрирующий ситуацию: {situation}. Ответ игрока: {answer}."


# ---------- Генератор изображений ----------
class GameImageGenerator:
    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        """Попытка сгенерировать картинку через Pollinations API."""
        url = f"https://image.pollinations.ai/prompt/{prompt}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return BytesIO(await resp.read())
        except Exception:
            return None
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        """Попытка сгенерировать картинку через NanoBanana API (пример)."""
        if not NANO_API_KEY:
            return None
        url = "https://api.nanobanana.com/generate"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {NANO_API_KEY}"},
                    json={"prompt": prompt, "size": "512x512"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        img_url = data.get("url")
                        if img_url:
                            async with session.get(img_url) as img_resp:
                                return BytesIO(await img_resp.read())
        except Exception:
            return None
        return None

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        """Отправка иллюстрации для ситуации и ответа."""
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False

        prompt = create_prompt(situation, answer)

        # Попытка через OpenAI
        img = None
        try:
            img_resp = await openai.Image.acreate(
                prompt=prompt,
                n=1,
                size="512x512"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(img_resp.data[0].url) as resp:
                    img_bytes = await resp.read()
                    img = BytesIO(img_bytes)
        except Exception:
            # Фолбэк на другие сервисы
            img = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)

        if not img:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
            return False

        await bot.send_photo(chat_id, BufferedInputFile(img.getvalue(), filename="illustration.png"))
        return True


# ---------- Генератор видео ----------
class GameVideoGenerator:
    async def _try_pollo_video(self, prompt: str) -> Optional[str]:
        """Попытка сгенерировать видео через PollO.ai."""
        if not POLLO_API_KEY:
            return None
        url = "https://api.pollo.ai/generate"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {POLLO_API_KEY}"},
                    json={"prompt": prompt}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("video_url")
        except Exception:
            return None
        return None

    async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
        """Отправка видео для ситуации и ответа."""
        prompt = create_video_prompt(situation, answer)

        # Пока основа — PollO.ai
        url = await self._try_pollo_video(prompt)

        if not url:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать видео.")
            return False

        await bot.send_video(chat_id, url)
        return True
