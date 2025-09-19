# game_utils.py — чтение JSON из корня проекта + исправленный перевод в видео-промпте
import os
import json
import random
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import asyncio
import aiohttp
import base64
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# Ключи
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NANO_API_KEY   = os.getenv("NANO_API_KEY")
HORDE_API_KEY  = os.getenv("HORDE_API_KEY")
POLLO_API_KEY  = os.getenv("POLLO_API_KEY")

# ---------- Промпты ----------
def _translate_to_en(text: str) -> str:
    if any(ord(c) > 127 for c in text):
        try:
            from googletrans import Translator
            translator = Translator()
            return translator.translate(text, dest="en").text
        except Exception:
            return text
    return text

def create_prompt(situation: str, answer: str) -> str:
    situation_clean = situation.replace("_____", "").replace("____", "").strip()
    situation_en = _translate_to_en(situation_clean)
    answer_en = _translate_to_en(answer.strip())
    styles = ["cartoon", "caricature", "comic panel", "flat colors"]
    perspectives = ["wide shot", "close-up", "medium shot", "bird's eye view", "low angle"]
    emotions = ["amused expression", "surprised look", "confused face", "happy smile", "shocked expression", "thoughtful pose"]
    return f"{situation_en} - {answer_en}, {random.choice(styles)}, {random.choice(perspectives)}, {random.choice(emotions)}, colorful, simple shapes, expressive"

def create_video_prompt(situation: str, answer: str) -> str:
    situation_clean = situation.replace("_____", "").replace("____", "").strip()
    situation_en = _translate_to_en(situation_clean)
    answer_en = _translate_to_en(answer.strip())
    motion_scenarios = [
        f"Person interacting with {answer_en} while thinking about: {situation_en}",
        f"Dynamic scene showing {answer_en} in action, representing: {situation_en}",
        f"Animated sequence of {answer_en} responding to: {situation_en}",
        f"Character discovering {answer_en} in context of: {situation_en}",
        f"Humorous scene with {answer_en} solving problem: {situation_en}"
    ]
    motion_styles = ["smooth animation", "bouncy movement", "dramatic zoom", "gentle pan", "dynamic rotation"]
    return f"6-second cartoon video: {random.choice(motion_scenarios)}, {random.choice(motion_styles)}, colorful, expressive characters, simple animation style"

# ---------- Колоды ----------
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json", base: Path | None = None):
        # База — корень проекта (на уровень выше utils)
        self.base_dir = base or Path(__file__).resolve().parent.parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str]    = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        for enc in ("utf-8-sig", "utf-8"):
            try:
                data = json.loads(file_path.read_text(encoding=enc))
                if isinstance(data, list):
                    # фильтр строк + удаление дублей
                    seen, out = set(), []
                    for x in data:
                        if isinstance(x, str):
                            x = x.strip()
                            if x and x not in seen:
                                seen.add(x); out.append(x)
                    return out
                return []
            except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
                continue
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Тестовая ситуация"

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = list(self.answers)
        random.shuffle(deck)
        return deck

decks = DeckManager()

# ---------- Изображения ----------
class GameImageGenerator:
    def __init__(self):
        self.nb_key = NANO_API_KEY

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=768&height=432"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=20) as r:
                    if r.status == 200:
                        return BytesIO(await r.read())
        except Exception:
            pass
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            return None
        url = "https://api.nanobanana.ai/v1/generate"
        payload = {"prompt": prompt, "model": "sdxl", "width": 768, "height": 432}
        headers = {"Authorization": f"Bearer {self.nb_key}"}
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

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False
        prompt = create_prompt(situation, answer)
        img = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)
        if not img:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
            return False
        img.seek(0)
        await bot.send_photo(chat_id, photo=BufferedInputFile(img.read(), filename="scene.jpg"))
        return True

# ---------- Видео (Pollo.ai) ----------
class GameVideoGenerator:
    def __init__(self):
        self.pollo_key = POLLO_API_KEY
        self.pollo_url = "https://pollo.ai/api/platform/generation/minimax/video-01"

    async def _try_pollo_video(self, prompt: str) -> Optional[str]:
        if not self.pollo_key:
            return None
        headers = {"Content-Type": "application/json", "x-api-key": self.pollo_key}
        try:
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
                    async with s.get(status_url, headers=headers, timeout=30) as st:
                        if st.status != 200:
                            continue
                        js = await st.json()
                        status = js.get("status") or js.get("state")
                        if status in ("completed", "succeeded", "success"):
                            out = js.get("output") or {}
                            if isinstance(out, dict):
                                return out.get("url") or out.get("video_url")
                            lst = js.get("outputs") or js.get("result") or []
                            for it in lst or []:
                                if isinstance(it, dict) and (it.get("url") or it.get("video_url")):
                                    return it.get("url") or it.get("video_url")
                            return js.get("url") or js.get("videoUrl")
                        if status in ("failed", "error"):
                            return None
        except Exception:
            return None
        return None

    async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
        prompt = create_video_prompt(situation, answer)
        url = await self._try_pollo_video(prompt)
        if not url:
            return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=180) as r:
                    if r.status != 200:
                        return False
                    data = await r.read()
            await bot.send_video(chat_id, video=BufferedInputFile(data, filename="round.mp4"), caption=answer, duration=6)
            return True
        except Exception:
            return False

gen = GameImageGenerator()
video_gen = GameVideoGenerator()
