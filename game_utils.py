# game_utils.py – ФИНАЛЬНАЯ ВЕРСИЯ С ENV-ПЕРЕМЕННЫМИ И ТРЕМЯ BACKEND

import os
import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
import base64
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# Загружаем переменные окружения из .env
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")


def create_pollinations_prompt(situation: str, answer: str) -> str:
    """
    Создает оптимизированный английский промпт для Pollinations.ai
    """
    combined = situation.replace("____", answer).strip().replace(".", "").replace(",", "")
    quick = {
        "На вечеринке": "at a party",
        "опоздать": "being late",
        "холодильник": "refrigerator",
        "кот в сапогах": "Puss in Boots",
    }
    text = combined
    for ru, en in quick.items():
        text = text.replace(ru, en)
    if any(ord(c) > 127 for c in text):
        try:
            from googletrans import Translator
            tr = Translator()
            text = tr.translate(combined, dest="en").text
        except:
            pass
    mods = "photorealistic cinematic lighting ultra detailed 8k trending on Artstation"
    return f"A photorealistic cinematic photo of {text}, {mods}"


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        # API-настройки
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except:
            pass
        return [
            "На вечеринке я неожиданно ____.",
            "Самая распространенная причина опоздать: ____.",
            "Мой секретный талант — ____."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            return None
        payload = {
            "prompt": prompt,
            "model": "sdxl",
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg_scale": 7.0
        }
        headers = {
            "Authorization": f"Bearer {self.nb_key}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(self.nb_url, json=payload, headers=headers, timeout=30)
                if resp.status == 200:
                    j = await resp.json()
                    url = j.get("image_url")
                    if url:
                        img_resp = await session.get(url)
                        if img_resp.status == 200:
                            return BytesIO(await img_resp.read())
        except:
            pass
        return None

    async def _try_horde(self, prompt: str) -> Optional[BytesIO]:
        if not self.horde_key:
            return None
        payload = {
            "prompt": prompt,
            "params": {
                "sampler_name": "k_euler",
                "cfg_scale": 7.0,
                "height": 512,
                "width": 512,
                "steps": 20,
                "n": 1
            },
            "nsfw": False,
            "trustedworkers": True,
            "models": ["Deliberate"],
            "r2": True,
            "shared": False,
            "replacement_filter": True
        }
        headers = {
            "apikey": self.horde_key,
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(f"{self.horde_url}/generate/async",
                                          json=payload, headers=headers)
                if resp.status != 202:
                    return None
                result = await resp.json()
                job = result.get("id")
                if not job:
                    return None
                for _ in range(30):
                    await asyncio.sleep(3)
                    check_resp = await session.get(f"{self.horde_url}/generate/check/{job}",
                                                   headers=headers)
                    if check_resp.status != 200:
                        continue
                    data = await check_resp.json()
                    if data.get("done"):
                        gens = data.get("generations", [])
                        if gens and gens[0].get("img"):
                            return BytesIO(base64.b64decode(gens[0]["img"]))
        except:
            pass
        return None

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url, timeout=10)
                if resp.status == 200:
                    return BytesIO(await resp.read())
        except:
            pass
        return None

    async def generate_and_send_image(
        self,
        bot: Bot,
        chat_id: int,
        situation: str,
        answer: Optional[str] = None
    ) -> bool:
        prompt = create_pollinations_prompt(situation, answer) if answer else "A photorealistic image masterpiece best quality"

        # 1) Nano Banana
        img = await self._try_nanobanana(prompt)
        if img:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=img.read(), filename="nb_image.jpeg"),
                caption=f"NanoBanana: {prompt}"
            )
            return True

        # 2) AI Horde
        try:
            img = await asyncio.wait_for(self._try_horde(prompt), timeout=60)
            if img:
                await bot.send_photo(
                    chat_id,
                    photo=BufferedInputFile(file=img.read(), filename="horde_image.jpeg"),
                    caption=f"AI Horde: {prompt}"
                )
                return True
        except asyncio.TimeoutError:
            pass

        # 3) Pollinations fallback
        img = await self._try_pollinations(prompt)
        if img:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=img.read(), filename="poll_image.jpeg"),
                caption=f"Pollinations: {prompt}"
            )
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение ни одним сервисом.")
        return False


# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
