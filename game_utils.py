import json
import random
from pathlib import Path
from io import BytesIO
import asyncio
import aiohttp
import os
import base64

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot
from aiogram.types import BufferedInputFile

# Ключи из .env
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NANO_API_KEY   = os.getenv("NANO_API_KEY")
HORDE_API_KEY  = os.getenv("HORDE_API_KEY")
POLLO_API_KEY  = os.getenv("POLLO_API_KEY")


class DeckManager:
    def __init__(self, sit_file="situations.json", ans_file="answers.json", base: Path | None = None):
        # Корень проекта (на уровень выше utils)
        self.base = base or Path(__file__).parent.parent
        self.situations = self._load(self.base / sit_file)
        self.answers    = self._load(self.base / ans_file)

    def _load(self, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Оставляем только строки
            items = [str(x).strip() for x in data if isinstance(x, str)]
            # Убираем дубли, сохраняя порядок
            seen = set()
            uniq = []
            for x in items:
                if x and x not in seen:
                    seen.add(x)
                    uniq.append(x)
            return uniq
        except Exception:
            return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Нет ситуаций"

    def get_new_shuffled_answers_deck(self):
        deck = list(self.answers)  # уже без дублей
        random.shuffle(deck)
        return deck


# Читает situations.json и answers.json из корня
decks = DeckManager(sit_file="situations.json", ans_file="answers.json")


async def send_illustration(bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
    prompt = f"{situation} — {answer}, high quality, realistic, cinematic lighting, 16:9"
    # 1) Gemini
    img = await _try_gemini_image(prompt)
    # 2) Фолбэки
    if not img:
        img = await _try_horde(prompt) or await _try_nanobanana(prompt)
    if not img:
        return False
    img.seek(0)
    await bot.send_photo(chat_id, photo=BufferedInputFile(img.read(), filename="scene.png"))
    return True


async def _try_gemini_image(prompt: str) -> BytesIO | None:
    if not GOOGLE_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "image/png"}
    }
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers, timeout=90) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                cands = data.get("candidates") or []
                if not cands:
                    return None
                parts = cands[0].get("content", {}).get("parts", [])
                if not parts:
                    return None
                inline = parts[0].get("inlineData") or {}
                b64 = inline.get("data")
                if not b64:
                    return None
                return BytesIO(base64.b64decode(b64))
    except Exception:
        return None


async def _try_nanobanana(prompt: str) -> BytesIO | None:
    if not NANO_API_KEY:
        return None
    url = "https://api.nanobanana.ai/v1/generate"
    headers = {"Authorization": f"Bearer {NANO_API_KEY}"}
    payload = {"prompt": prompt, "model": "sdxl", "width": 768, "height": 432}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers, timeout=60) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                img_url = data.get("image_url")
            if not img_url:
                return None
            async with s.get(img_url, timeout=60) as g:
                if g.status != 200:
                    return None
                return BytesIO(await g.read())
    except Exception:
        return None


async def _try_horde(prompt: str) -> BytesIO | None:
    if not HORDE_API_KEY:
        return None
    start = "https://aihorde.net/api/v2/generate/async"
    check = "https://aihorde.net/api/v2/generate/check/"
    headers = {"apikey": HORDE_API_KEY}
    payload = {"prompt": prompt, "params": {"width": 768, "height": 432}}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(start, json=payload, headers=headers, timeout=30) as r:
                j = await r.json()
                task = j.get("id")
                if not task:
                    return None
            for _ in range(40):
                await asyncio.sleep(2)
                async with s.get(check + task, headers=headers, timeout=15) as st:
                    js = await st.json()
                    if js.get("done"):
                        imgs = js.get("images") or []
                        if not imgs:
                            return None
                        img_url = imgs[0]
                        async with s.get(img_url, timeout=60) as g:
                            if g.status != 200:
                                return None
                            return BytesIO(await g.read())
    except Exception:
        return None
    return None


class GameVideoGenerator:
    def __init__(self):
        self.url = "https://pollo.ai/api/platform/generation/minimax/video-01"
        self.key = POLLO_API_KEY

    async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
        if not self.key:
            return False
        prompt = f"6s cinematic b-roll, realistic: {situation} — {answer}"
        headers = {"x-api-key": self.key}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(self.url, json={"input": {"prompt": prompt}}, headers=headers, timeout=90) as r:
                    js = await r.json()
                    tid = js.get("taskId")
                    if not tid:
                        return False
                status = f"https://pollo.ai/api/platform/generation/{tid}/status"
                for _ in range(60):
                    await asyncio.sleep(5)
                    async with s.get(status, headers=headers, timeout=30) as st:
                        sj = await st.json()
                        if sj.get("status") == "succeeded":
                            out = sj.get("output", {})
                            vid_url = out.get("url") or (out[0] if isinstance(out, list) else {}).get("url")
                            if not vid_url:
                                return False
                            async with s.get(vid_url, timeout=120) as g:
                                if g.status != 200:
                                    return False
                                data = await g.read()
                                await bot.send_video(chat_id, video=BufferedInputFile(data, filename="round.mp4"))
                                return True
        except Exception:
            return False
        return False


# Экземпляр для импорта в handlers
video_gen = GameVideoGenerator()
