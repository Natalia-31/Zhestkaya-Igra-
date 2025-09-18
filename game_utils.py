# game_utils.py

import json
import random
from pathlib import Path
from io import BytesIO
import asyncio
import aiohttp

from dotenv import load_dotenv
load_dotenv()

# Поддержка разных провайдеров
from aiogram import Bot
from aiogram.types import BufferedInputFile

# Инициализация ключей из .env
import os
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
POLLO_API_KEY = os.getenv("POLLO_API_KEY")


class DeckManager:
    def __init__(self,
                 sit_file="situations.json",
                 ans_file="answers.json"):
        base = Path(__file__).parent
        # Используем ваши файлы из корня проекта
        self.situations = self._load(base / sit_file)
        self.answers    = self._load(base / ans_file)

    def _load(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Нет ситуаций"

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy() if self.answers else []
        random.shuffle(deck)
        return deck


decks = DeckManager(
    sit_file="situations.json",
    ans_file="answers.json"
)


async def send_illustration(bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
    prompt = f"{situation} — {answer}, cartoon style, simple shapes"
    # Попытка через Horde
    img = await _try_horde(prompt)
    if not img:
        img = await _try_nanobanana(prompt)
    if img:
        img.seek(0)
        await bot.send_photo(chat_id,
                             photo=BufferedInputFile(img.read(), filename="scene.png"))
        return True
    return False


async def _try_nanobanana(prompt: str) -> BytesIO | None:
    if not NANO_API_KEY:
        return None
    url = "https://api.nanobanana.ai/v1/generate"
    headers = {"Authorization": f"Bearer {NANO_API_KEY}"}
    payload = {"prompt": prompt, "model": "sdxl", "width": 512, "height": 512}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            img_url = data.get("image_url")
        if not img_url:
            return None
        async with session.get(img_url, timeout=30) as r:
            if r.status != 200:
                return None
            buf = BytesIO(await r.read())
            return buf


async def _try_horde(prompt: str) -> BytesIO | None:
    if not HORDE_API_KEY:
        return None
    start = "https://aihorde.net/api/v2/generate/async"
    check = "https://aihorde.net/api/v2/generate/check/"
    headers = {"apikey": HORDE_API_KEY}
    payload = {"prompt": prompt, "params": {"width": 512, "height": 512}}
    async with aiohttp.ClientSession() as session:
        async with session.post(start, json=payload, headers=headers, timeout=30) as resp:
            task = (await resp.json()).get("id")
        for _ in range(30):
            await asyncio.sleep(2)
            async with session.get(check + task, headers=headers, timeout=10) as st:
                data = await st.json()
                if data.get("done"):
                    img_url = data["images"][0]
                    async with session.get(img_url, timeout=20) as img_r:
                        return BytesIO(await img_r.read())
    return None


class GameVideoGenerator:
    def __init__(self):
        self.url = "https://pollo.ai/api/platform/generation/minimax/video-01"
        self.key = POLLO_API_KEY

    async def send_video_illustration(self, bot: Bot, chat_id: int,
                                      situation: str, answer: str) -> bool:
        prompt = f"6s cartoon: {situation} — {answer}"
        if not self.key:
            return False
        headers = {"x-api-key": self.key}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json={"input": {"prompt": prompt}}, headers=headers, timeout=60) as resp:
                data = await resp.json()
                tid = data.get("taskId")
            status_url = f"https://pollo.ai/api/platform/generation/{tid}/status"
            for _ in range(40):
                await asyncio.sleep(5)
                async with session.get(status_url, headers=headers, timeout=30) as st:
                    sd = await st.json()
                    if sd.get("status") == "succeeded":
                        out = sd.get("output", {})
                        vid_url = out.get("url") or (out[0] if isinstance(out, list) else {}).get("url")
                        if vid_url:
                            async with session.get(vid_url, timeout=60) as v:
                                data = await v.read()
                                await bot.send_video(chat_id,
                                                     video=BufferedInputFile(data, filename="vid.mp4"),
                                                     duration=6)
                                return True
        return False


video_gen = GameVideoGenerator()
