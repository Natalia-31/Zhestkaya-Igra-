# game_utils.py — ситуации/ответы из JSON + генерация изображений без OpenAI (Pollinations → AI Horde → NanoBanana)

import os
import json
import random
from pathlib import Path
from typing import List, Optional

import asyncio
import aiohttp
import aiofiles
from aiogram import Bot
from aiogram.types import FSInputFile

class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        for enc in ("utf-8", "utf-8-sig"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc}): {len(data)} из {file_path}")
                    return data
                else:
                    print(f"⚠️ {file_path} ({label}) не список.")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path} ({label})")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Кодировка {enc} не подошла: {e}, пробуем следующую…")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON {file_path}: {e}")
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка при чтении {file_path}: {e}")
                return []
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "На вечеринке я неожиданно ____."

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck


class GameImageGenerator:
    """
    Последовательно пробует провайдеры:
      1) Pollinations (без ключа)
      2) AI Horde (env: HORDE_API_KEY)
      3) NanoBanana (env: NANOBANANA_API_KEY)
    Возвращает первую успешно полученную картинку.
    """
    def __init__(self, images_dir: str = "generated_images"):
        self.base_dir = Path(__file__).resolve().parent
        self.images_dir = (self.base_dir / images_dir).resolve()
        self.images_dir.mkdir(parents=True, exist_ok=True)

        self.HORDE_API_KEY = os.getenv("HORDE_API_KEY", "")
        self.NANOBANANA_API_KEY = os.getenv("NANOBANANA_API_KEY", "")
        self.timeout = aiohttp.ClientTimeout(total=180)

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        prompt = self._build_prompt(situation, answer)
        out = self.images_dir / f"img_{random.randint(1000,9999)}.png"

        ok = await self._try_pollinations(prompt, out)
        if not ok and self.HORDE_API_KEY:
            ok = await self._try_horde(prompt, out)
        if not ok and self.NANOBANANA_API_KEY:
            ok = await self._try_nanobanana(prompt, out)

        if ok and out.exists():
            await bot.send_photo(chat_id, FSInputFile(out))
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
        return False

    def _build_prompt(self, situation: str, answer: Optional[str]) -> str:
        base = situation.replace("____", answer or "неожиданный поворот")
        # Короткий, устойчивый промпт
        return f"{base}, cartoon, vibrant, colorful, high quality"

    async def _try_pollinations(self, prompt: str, out_path: Path) -> bool:
        from urllib.parse import quote
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.get(url) as r:
                    if r.status == 200 and r.content_type.startswith("image/"):
                        async with aiofiles.open(out_path, "wb") as f:
                            async for chunk in r.content.iter_chunked(8192):
                                await f.write(chunk)
                        return True
        except Exception as e:
            print(f"⚠️ Pollinations: {e}")
        return False

    async def _try_horde(self, prompt: str, out_path: Path) -> bool:
        # Примерный флоу AI Horde (Stable Horde). При необходимости адаптируйте под ваш аккаунт/эндвпоинт.
        base = "https://stablehorde.net/api/v2"
        headers = {"apikey": self.HORDE_API_KEY, "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "params": {"width": 768, "height": 768, "sampler_name": "k_euler", "steps": 25}
        }
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.post(f"{base}/generate/async", json=payload, headers=headers) as r:
                    if r.status != 202:
                        return False
                    data = await r.json()
                    job_id = data.get("id")
                    if not job_id:
                        return False

                # Опрос статуса
                for _ in range(90):  # до ~3 минут
                    await asyncio.sleep(2)
                    async with aiohttp.ClientSession(timeout=self.timeout) as s2:
                        async with s2.get(f"{base}/generate/status/{job_id}", headers=headers) as rr:
                            if rr.status != 200:
                                continue
                            st = await rr.json()
                            if st.get("done"):
                                gens = st.get("generations") or []
                                if not gens:
                                    return False
                                img_url = gens[0].get("img")
                                if not img_url:
                                    return False
                                async with s2.get(img_url) as ir:
                                    if ir.status == 200 and ir.content_type.startswith("image/"):
                                        async with aiofiles.open(out_path, "wb") as f:
                                            async for chunk in ir.content.iter_chunked(8192):
                                                await f.write(chunk)
                                        return True
                return False
        except Exception as e:
            print(f"⚠️ AI Horde: {e}")
            return False

    async def _try_nanobanana(self, prompt: str, out_path: Path) -> bool:
        # Шаблон под кастомный REST провайдер; замените URL/формат на свой.
        url = "https://api.nanobanana.ai/v1/generate"
        headers = {"Authorization": f"Bearer {self.NANOBANANA_API_KEY}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "size": "1024x1024"}
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.post(url, json=payload, headers=headers) as r:
                    if r.status != 200:
                        return False
                    data = await r.json()
                    img_url = data.get("url")
                    if not img_url:
                        return False
            async with aiohttp.ClientSession(timeout=self.timeout) as s2:
                async with s2.get(img_url) as ir:
                    if ir.status == 200 and ir.content_type.startswith("image/"):
                        async with aiofiles.open(out_path, "wb") as f:
                            async for chunk in ir.content.iter_chunked(8192):
                                await f.write(chunk)
                        return True
        except Exception as e:
            print(f"⚠️ NanoBanana: {e}")
        return False


# Экспорт для хэндлеров
decks = DeckManager()
gen = GameImageGenerator()
