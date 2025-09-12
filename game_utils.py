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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")  # Нужно получить отдельно


def create_prompt(situation: str, answer: str) -> str:
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
            translator = Translator()
            text = translator.translate(combined, dest='en').text
        except Exception:
            pass
    modifiers = "photorealistic cinematic lighting ultra detailed 8k trending on Artstation"
    return f"{text}, {modifiers}"


class GameImageGenerator:
    def __init__(self, situations_file="situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"
        self.replicate_token = REPLICATE_API_TOKEN

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return ["На вечеринке я неожиданно ____."]

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
            "cfg_scale": 7.0,
        }
        headers = {
            "Authorization": f"Bearer {self.nb_key}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(self.nb_url, json=payload, headers=headers, timeout=20)
                if resp.status != 200:
                    return None
                data = await resp.json()
                url = data.get("image_url")
                if not url:
                    return None
                img_resp = await session.get(url, timeout=20)
                if img_resp.status != 200:
                    return None
                return BytesIO(await img_resp.read())
        except Exception:
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
            "replacement_filter": True,
        }
        headers = {
            "apikey": self.horde_key,
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(f"{self.horde_url}/generate/async", json=payload, headers=headers, timeout=20)
                if resp.status != 202:
                    return None
                result = await resp.json()
                job = result.get("id")
                if not job:
                    return None
                for _ in range(20):
                    await asyncio.sleep(3)
                    check_resp = await session.get(f"{self.horde_url}/generate/check/{job}", headers=headers, timeout=10)
                    if check_resp.status != 200:
                        continue
                    check_result = await check_resp.json()
                    if check_result.get("done"):
                        generations = check_result.get("generations", [])
                        if generations and generations[0].get("img"):
                            return BytesIO(base64.b64decode(generations[0]["img"]))
        except Exception:
            return None

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url, timeout=10)
                if resp.status != 200:
                    return None
                return BytesIO(await resp.read())
        except Exception:
            return None

    async def _try_replicate(self, prompt: str) -> Optional[BytesIO]:
        if not self.replicate_token:
            return None
        headers = {
            "Authorization": f"Token {self.replicate_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "version": "db21e45d39c8d5eec3b3f8f1539e0e48fe406a5a4e9f05c5246e149aef97a9f3",  # stable-diffusion-v1.5 example
            "input": {"prompt": prompt, "width": 512, "height": 512}
        }
        try:
            async with aiohttp.ClientSession() as session:
                create_resp = await session.post("https://api.replicate.com/v1/predictions", json=payload, headers=headers)
                if create_resp.status != 201:
                    return None
                creation_result = await create_resp.json()
                prediction_url = creation_result["urls"]["get"]
                # Пуллим статус задачи
                for _ in range(20):
                    await asyncio.sleep(3)
                    status_resp = await session.get(prediction_url, headers=headers)
                    if status_resp.status != 200:
                        continue
                    status_data = await status_resp.json()
                    if status_data["status"] == "succeeded":
                        output_urls = status_data["output"]
                        if output_urls:
                            img_resp = await session.get(output_urls[0])
                            if img_resp.status == 200:
                                return BytesIO(await img_resp.read())
                        break
                    elif status_data["status"] == "failed":
                        break
        except Exception:
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        prompt = create_prompt(situation, answer) if answer else "A photorealistic image masterpiece best quality"

        coroutines = [
            self._try_nanobanana(prompt),
            self._try_horde(prompt),
            self._try_pollinations(prompt),
            self._try_replicate(prompt)
        ]

        # Запускаем все параллельно и ждём первого результата
        done, pending = await asyncio.wait(coroutines, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        for task in done:
            img = task.result()
            if img:
                await bot.send_photo(
                    chat_id,
                    photo=BufferedInputFile(file=img.read(), filename="generated_image.jpeg"),
                    caption=f"Generated by one of the services: {prompt}"
                )
                return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение ни одним из сервисов.")
        return False


gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
