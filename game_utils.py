import os
import json
import random
import asyncio
from io import BytesIO
from pathlib import Path
import aiohttp
from urllib.parse import quote
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

load_dotenv()
# API Keys from .env
NANO_API_KEY       = os.getenv("NANO_API_KEY")
HORDE_API_KEY      = os.getenv("HORDE_API_KEY")
POLLO_API_KEY      = os.getenv("POLLO_API_KEY")
REPLICATE_API_TOKEN= os.getenv("REPLICATE_API_TOKEN")

# ─── DeckManager ──────────────────────────────────────────────────────────────
class DeckManager:
    def __init__(self, sit_file="situations.json", ans_file="answers.json"):
        base = Path(__file__).parent
        self.situations = self._load(base / sit_file)
        self.answers    = self._load(base / ans_file)
    def _load(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return []
    def get_random_situation(self):
        return random.choice(self.situations) if self.situations else ""
    def get_new_shuffled_answers_deck(self):
        deck = self.answers.copy(); random.shuffle(deck); return deck

decks = DeckManager()


# ─── Prompt builders ──────────────────────────────────────────────────────────
def create_prompt(situation: str, answer: str) -> str:
    base = f"{situation.strip()} — {answer.strip()}"
    return f"{base}, cartoon style, flat colors, simple shapes"

def create_video_prompt(situation: str, answer: str) -> str:
    base = f"{situation.strip()} — {answer.strip()}"
    return f"6s cartoon video: {base}, smooth animation, simple characters"


# ─── Nanobanana ───────────────────────────────────────────────────────────────
async def _try_nanobanana(prompt: str) -> BytesIO | None:
    if not NANO_API_KEY: return None
    url = "https://api.nanobanana.ai/v1/generate"
    headers = {"Authorization": f"Bearer {NANO_API_KEY}", "Content-Type": "application/json"}
    payload = {"prompt":prompt,"model":"sdxl","width":512,"height":512,"steps":20,"cfg_scale":7.0}
    async with aiohttp.ClientSession() as s:
        async with s.post(url,json=payload,headers=headers,timeout=60) as r:
            if r.status!=200: return None
            data = await r.json()
            img_url = data.get("image_url") or data.get("url")
        if not img_url: return None
        async with s.get(img_url,timeout=30) as r2:
            if r2.status!=200: return None
            return BytesIO(await r2.read())

# ─── AI Horde ────────────────────────────────────────────────────────────────
async def _try_horde(prompt: str) -> BytesIO | None:
    if not HORDE_API_KEY: return None
    start = "https://aihorde.net/api/v2/generate/async"
    check = "https://aihorde.net/api/v2/generate/check/"
    hdr = {"apikey":HORDE_API_KEY}
    payload = {"prompt":prompt,"params":{"width":512,"height":512,"sampler_name":"k_euler_ancestral"}}
    async with aiohttp.ClientSession() as s:
        async with s.post(start,json=payload,headers=hdr,timeout=30) as r:
            jd = await r.json(); task=jd.get("id")
        for _ in range(30):
            await asyncio.sleep(2)
            async with s.get(check+task,headers=hdr,timeout=10) as st:
                sd = await st.json()
                if sd.get("done"):
                    url = sd["images"][0]
                    async with s.get(url,timeout=20) as img:
                        return BytesIO(await img.read())
    return None

# ─── Pollo.ai Video ─────────────────────────────────────────────────────────
class GameVideoGenerator:
    def __init__(self):
        self.key = POLLO_API_KEY
        self.url = "https://pollo.ai/api/platform/generation/minimax/video-01"
    async def _try_pollo(self, prompt: str) -> str | None:
        if not self.key: return None
        hdr = {"x-api-key":self.key,"Content-Type":"application/json"}
        async with aiohttp.ClientSession() as s:
            async with s.post(self.url,json={"input":{"prompt":prompt}},headers=hdr,timeout=60) as r:
                j = await r.json(); tid = j.get("taskId") or j.get("id")
            status = f"https://pollo.ai/api/platform/generation/{tid}/status"
            for _ in range(30):
                await asyncio.sleep(10)
                async with s.get(status,headers=hdr,timeout=30) as st:
                    sd=await st.json()
                    if sd.get("status") in ("completed","succeeded"):
                        out=sd.get("output") or sd.get("outputs") or {}
                        url = (out.get("url") if isinstance(out,dict) else out[0].get("url"))
                        return url
        return None

    async def send_video(self,bot:Bot,chat_id:int,sit:str,ans:str)->bool:
        prompt = create_video_prompt(sit,ans)
        url = await self._try_pollo(prompt)
        if not url: return False
        async with aiohttp.ClientSession() as s:
            async with s.get(url,timeout=60) as r:
                if r.status==200:
                    data=await r.read()
                    await bot.send_video(chat_id,video=BufferedInputFile(data,"vid.mp4"),duration=6)
                    return True
        return False

video_gen = GameVideoGenerator()


# ─── Image sender ────────────────────────────────────────────────────────────
async def send_illustration(bot:Bot,chat_id:int,sit:str,ans:str)->bool:
    prompt = create_prompt(sit,ans)
    tasks = [
        _try_horde(prompt),
        _try_nanobanana(prompt),
    ]
    for coro in asyncio.as_completed(tasks):
        buf = await coro
        if buf:
            buf.seek(0)
            await bot.send_photo(chat_id, photo=BufferedInputFile(buf.read(),filename="scene.png"))
            return True
    return False
