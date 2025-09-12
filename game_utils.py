# game_utils.py — ВЕРСИЯ ТОЛЬКО С NANO BANANA

import os
import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# Загружаем ключ из .env
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")

def create_nano_prompt(situation: str, answer: str) -> str:
    """
    Составляет краткий английский промпт для Nano Banana
    """
    combined = situation.replace("____", answer).strip().replace(".", "").replace(",", "")
    quick = {"На вечеринке": "at a party", "опоздать": "being late", "холодильник": "refrigerator", "кот в сапогах": "Puss in Boots"}
    text = combined
    for ru, en in quick.items():
        text = text.replace(ru, en)
    if any(ord(c) > 127 for c in text):
        try:
            from googletrans import Translator
            tr = Translator()
            text = tr.translate(combined, dest="en").text
        except Exception as e:
            print(f"[Translate error] {e}")
    mods = "photorealistic, cinematic lighting, ultra detailed, 8k, trending on Artstation"
    return f"{text}, {mods}"

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return ["На вечеринке я неожиданно ____."]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def generate_image_with_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            print("🚫 NanoBanana: missing API key")
            return None
        print(f"🔎 NanoBanana: generating: {prompt}")
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
                print(f"🔍 NanoBanana status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("image_url")
                    if url:
                        img_resp = await session.get(url, timeout=30)
                        if img_resp.status == 200:
                            print("✅ NanoBanana: success")
                            return BytesIO(await img_resp.read())
        except Exception as e:
            print(f"❌ NanoBanana error: {e}")
        return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        prompt = create_nano_prompt(situation, answer) if answer else "photorealistic masterpiece"
        img = await self.generate_image_with_nanobanana(prompt)
        if img:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=img.read(), filename="nano_image.jpeg"),
                caption=f"NanoBanana prompt: {prompt}"
            )
            return True
        await bot.send_message(chat_id, "⚠️ Nano Banana недоступен или возникла ошибка при генерации.")
        return False

gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
