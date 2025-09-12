# game_utils.py – С ДЕБАГ-ЛОГАМИ

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

load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")


def create_pollinations_prompt(situation: str, answer: str) -> str:
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
            print(f"🔄 [Translate] {combined} -> {text}")
        except Exception as e:
            print(f"⚠️ [Translate error] {e}")
    mods = "photorealistic cinematic lighting ultra detailed 8k trending on Artstation"
    prompt = f"A photorealistic cinematic photo of {text}, {mods}"
    print(f"📝 [Prompt] {prompt}")
    return prompt


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return ["На вечеринке я неожиданно ____."]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            print("🚫 NanoBanana: missing API key")
            return None
        print("🔎 NanoBanana: trying...")
        payload = {"prompt": prompt, "model": "sdxl", "width": 512, "height": 512, "steps": 15, "cfg_scale": 7.0}
        headers = {"Authorization": f"Bearer {self.nb_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(self.nb_url, json=payload, headers=headers, timeout=10)
                print(f"🔍 NanoBanana status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("image_url")
                    if url:
                        img_resp = await session.get(url, timeout=10)
                        if img_resp.status == 200:
                            print("✅ NanoBanana: success")
                            return BytesIO(await img_resp.read())
        except Exception as e:
            print(f"❌ NanoBanana error: {e}")
        return None

    async def _try_horde(self, prompt: str) -> Optional[BytesIO]:
        if not self.horde_key:
            print("🚫 AI Horde: missing API key")
            return None
        print("🔎 AI Horde: trying...")
        payload = {
            "prompt": prompt,
            "params": {"sampler_name": "k_euler", "cfg_scale": 7.0, "height": 512, "width": 512, "steps": 15, "n": 1},
            "nsfw": False, "trustedworkers": True, "models": ["Deliberate"], "r2": True, "shared": False, "replacement_filter": True
        }
        headers = {"apikey": self.horde_key, "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(f"{self.horde_url}/generate/async", json=payload, headers=headers, timeout=10)
                print(f"🔍 Horde async status: {resp.status}")
                if resp.status != 202:
                    return None
                result = await resp.json()
                job = result.get("id")
                if not job:
                    return None
                for i in range(20):
                    await asyncio.sleep(2)
                    check = await session.get(f"{self.horde_url}/generate/check/{job}", headers=headers, timeout=5)
                    if check.status != 200:
                        continue
                    data = await check.json()
                    if data.get("done"):
                        gens = data.get("generations", [])
                        if gens and gens[0].get("img"):
                            print("✅ AI Horde: success")
                            return BytesIO(base64.b64decode(gens[0]["img"]))
        except Exception as e:
            print(f"❌ AI Horde error: {e}")
        return None

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        print("🔎 Pollinations: trying...")
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url, timeout=5)
                print(f"🔍 Pollinations status: {resp.status}")
                if resp.status == 200:
                    print("✅ Pollinations: success")
                    return BytesIO(await resp.read())
        except Exception as e:
            print(f"❌ Pollinations error: {e}")
        return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        prompt = create_pollinations_prompt(situation, answer) if answer else "A photorealistic image masterpiece best quality"

        # Nano Banana
        img = await self._try_nanobanana(prompt)
        if img:
            await bot.send_photo(chat_id, photo=BufferedInputFile(file=img.read(), filename="nb.jpeg"))
            return True

        # AI Horde
        img = await self._try_horde(prompt)
        if img:
            await bot.send_photo(chat_id, photo=BufferedInputFile(file=img.read(), filename="horde.jpeg"))
            return True

        # Pollinations
        img = await self._try_pollinations(prompt)
        if img:
            await bot.send_photo(chat_id, photo=BufferedInputFile(file=img.read(), filename="poll.jpeg"))
            return True

        await bot.send_message(chat_id, "⚠️ Все три сервиса недоступны или возвращают ошибки.")
        return False


gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
