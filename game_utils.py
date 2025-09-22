import os
import json
import random
import asyncio
from pathlib import Path
from io import BytesIO
from typing import List, Optional

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_SETTINGS

# ====== Environment ======
load_dotenv()
NANO_API_KEY   = os.getenv("NANO_API_KEY")
POLLO_API_KEY  = os.getenv("POLLO_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан в окружении")

client = OpenAI(api_key=OPENAI_API_KEY)


# ====== Deck Manager ======
class DeckManager:
    def __init__(
        self,
        situations_file: str = "situations.json",
        answers_file: str = "answers.json",
        base: Path | None = None
    ):
        self.base_dir = base or Path(__file__).parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations = self._load_list(self.sit_path)
        self.answers    = self._load_list(self.ans_path)

    def _load_list(self, file_path: Path) -> List[str]:
        for enc in ("utf-8-sig", "utf-8"):
            try:
                data = json.loads(file_path.read_text(encoding=enc))
                if isinstance(data, list):
                    seen, out = set(), []
                    for x in data:
                        if isinstance(x, str):
                            x = x.strip()
                            if x and x not in seen:
                                seen.add(x)
                                out.append(x)
                    return out
            except Exception:
                continue
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Тестовая ситуация"

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = list(self.answers)
        random.shuffle(deck)
        return deck


# ====== Prompt Helpers ======
def _translate_to_en(text: str) -> str:
    if any(ord(c) > 127 for c in text):
        try:
            from googletrans import Translator
            return Translator().translate(text, dest="en").text
        except Exception:
            pass
    return text


def create_image_prompt(situation: str, answer: str) -> str:
    sit = _translate_to_en(situation.replace("_____", "").strip())
    ans = _translate_to_en(answer.strip())
    return f"{sit} - {ans}, cartoon, colorful, simple shapes, expressive"


def create_video_prompt(situation: str, answer: str) -> str:
    sit = _translate_to_en(situation.replace("_____", "").strip())
    ans = _translate_to_en(answer.strip())
    return (
        f"6-second cartoon: scene shows {ans} responding to {sit}, "
        "smooth animation, colorful, expressive characters"
    )


# ====== Image Generator ======
class GameImageGenerator:
    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{aiohttp.helpers.quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=20) as r:
                    if r.status == 200:
                        return BytesIO(await r.read())
        except Exception:
            pass
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not NANO_API_KEY:
            return None
        api_url = "https://api.nanobanana.ai/v1/generate"
        headers = {"Authorization": f"Bearer {NANO_API_KEY}"}
        payload = {"prompt": prompt, "model": "sdxl", "width": 512, "height": 512}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(api_url, json=payload, headers=headers, timeout=60) as r:
                    if r.status != 200:
                        return None
                    data = await r.json()
                    img_url = data.get("image_url") or data.get("url")
                if img_url:
                    async with aiohttp.ClientSession() as s2:
                        async with s2.get(img_url, timeout=60) as r2:
                            if r2.status == 200:
                                return BytesIO(await r2.read())
        except Exception:
            pass
        return None

    async def send_illustration(
        self,
        bot: Bot,
        chat_id: int,
        situation: str,
        answer: Optional[str] = None
    ) -> bool:
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False

        prompt = create_image_prompt(situation, answer)
        img_stream: Optional[BytesIO] = None

        # OpenAI Image API v1
        try:
            img_resp = await client.images.generate(prompt=prompt, n=1, size="512x512")
            url = img_resp.data[0].url
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=30) as r:
                    if r.status == 200:
                        img_stream = BytesIO(await r.read())
        except Exception:
            img_stream = None

        # Fallback
        if not img_stream:
            img_stream = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)

        if not img_stream:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
            return False

        img_stream.seek(0)
        await bot.send_photo(chat_id, photo=BufferedInputFile(img_stream.read(), filename="illustration.png"))
        return True


# ====== Video Generator ======
class GameVideoGenerator:
    def __init__(self):
        self.pollo_key = POLLO_API_KEY
        self.pollo_url = "https://pollo.ai/api/platform/generation/minimax/video-01"

    async def _try_pollo_video(self, prompt: str) -> Optional[str]:
        if not self.pollo_key:
            return None
        headers = {"Content-Type": "application/json", "x-api-key": self.pollo_key}
        async with aiohttp.ClientSession() as s:
            async with s.post(self.pollo_url, json={"input": {"prompt": prompt}}, headers=headers, timeout=60) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                task_id = data.get("taskId") or data.get("id")
        if not task_id:
            return None
        status_url = f"https://pollo.ai/api/platform/generation/{task_id}/status"
        for _ in range(36):
            await asyncio.sleep(10)
            async with aiohttp.ClientSession() as s2:
                async with s2.get(status_url, headers=headers, timeout=30) as st:
                    if st.status == 200:
                        js = await st.json()
                        status = js.get("status") or js.get("state")
                        if status in ("completed", "succeeded", "success"):
                            out = js.get("output") or {}
                            return out.get("url") or out.get("video_url")
                        if status in ("failed", "error"):
                            return None
        return None

    async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
        prompt = create_video_prompt(situation, answer)
        url = await self._try_pollo_video(prompt)
        if not url:
            return False
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=180) as r:
                if r.status != 200:
                    return False
                data = await r.read()
        await bot.send_video(chat_id, video=BufferedInputFile(data, filename="round.mp4"), caption=answer, duration=6)
        return True


# ====== Instances ======
decks = DeckManager(base=Path(__file__).resolve().parent)
image_gen = GameImageGenerator()
video_gen = GameVideoGenerator()
