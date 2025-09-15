# game_utils.py — колоды + генерация изображений без OpenAI (Pollinations / AI Horde / NanoBanana)

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


# -------------------- Менеджер колод (situations / answers) --------------------

class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.script_dir = Path(__file__).resolve().parent
        self.situations_path = (self.script_dir / situations_file).resolve()
        self.answers_path = (self.script_dir / answers_file).resolve()
        self.situations: List[str] = self._load_deck(self.situations_path, "situations")
        self.answers: List[str] = self._load_deck(self.answers_path, "answers")

    def _load_deck(self, file_path: Path, label: str) -> List[str]:
        for enc, enc_name in (("utf-8", "UTF-8"), ("utf-8-sig", "UTF-8-SIG")):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc_name}): {len(data)} карт из {file_path}")
                    return data
                else:
                    print(f"⚠️ Файл {file_path} ({label}) не содержит JSON-список")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path} ({label})")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Проблема кодировки {file_path} как {enc_name}: {e} — пробуем другую")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в {file_path} ({label}): {e}")
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка при чтении {file_path} ({label}): {e}")
                return []
        return []

    def get_random_situation(self) -> str:
        if not self.situations:
            return "На вечеринке я неожиданно ____."
        return random.choice(self.situations)

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck


# -------------------- Генератор изображений (Pollinations / AI Horde / NanoBanana) --------------------

class GameImageGenerator:
    """
    Параллельно пробует несколько провайдеров и возвращает первый успешный результат.
    Все сохраняется в generated_images/, затем отправляется в чат.
    """
    def __init__(self, images_dir: str = "generated_images"):
        self.script_dir = Path(__file__).resolve().parent
        self.images_dir = (self.script_dir / images_dir).resolve()
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Ключи/настройки провайдеров (если нужны)
        self.HORDE_API_KEY = os.getenv("HORDE_API_KEY", "")
        self.NANOBANANA_API_KEY = os.getenv("NANOBANANA_API_KEY", "")

        # Таймауты
        self.request_timeout = aiohttp.ClientTimeout(total=120)

    # ---------- Провайдер 1: Pollinations (простой и быстрый, без ключа) ----------
    async def _try_pollinations(self, prompt: str, out_path: Path) -> bool:
        # Док. по Pollinations часто встречается в формате: https://image.pollinations.ai/prompt/{prompt}
        # Для надежности кодируем пробелы и спецсимволы
        from urllib.parse import quote
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        try:
            async with aiohttp.ClientSession(timeout=self.request_timeout) as session:
                async with session.get(url) as r:
                    if r.status == 200 and r.content_type.startswith("image/"):
                        async with aiofiles.open(out_path, "wb") as f:
                            async for chunk in r.content.iter_chunked(8192):
                                await f.write(chunk)
                        return True
        except Exception as e:
            print(f"⚠️ Pollinations ошибка: {e}")
        return False

    # ---------- Провайдер 2: AI Horde ----------
    async def _try_horde(self, prompt: str, out_path: Path) -> bool:
        if not self.HORDE_API_KEY:
            return False
        # Примерный флоу: POST /generate, затем опрос по id до готовности, потом GET файла
        # Здесь упрощенный шаблон — замените эндпоинты на используемые в вашем аккаунте.
        base = "https://stablehorde.net/api/v2"
        headers = {"apikey": self.HORDE_API_KEY, "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "params": {"width": 768, "height": 768, "sampler_name": "k_euler", "steps": 25}
        }
        try:
            async with aiohttp.ClientSession(timeout=self.request_timeout) as session:
                async with session.post(f"{base}/generate/async", json=payload, headers=headers) as r:
                    if r.status != 202:
                        return False
                    data = await r.json()
                    job_id = data.get("id")
                    if not job_id:
                        return False

                # Опрос статуса
                for _ in range(60):  # до 60 * 2с = 120сек
                    await asyncio.sleep(2)
                    async with aiohttp.ClientSession(timeout=self.request_timeout) as session:
                        async with session.get(f"{base}/generate/status/{job_id}", headers=headers) as r:
                            if r.status != 200:
                                continue
                            st = await r.json()
                            if st.get("done"):
                                imgs = st.get("generations") or []
                                if not imgs:
                                    return False
                                # Берем первый URL результата
                                img_url = imgs.get("img")
                                if not img_url:
                                    return False
                                async with session.get(img_url) as ir:
                                    if ir.status == 200 and ir.content_type.startswith("image/"):
                                        async with aiofiles.open(out_path, "wb") as f:
                                            async for chunk in ir.content.iter_chunked(8192):
                                                await f.write(chunk)
                                        return True
                return False
        except Exception as e:
            print(f"⚠️ AI Horde ошибка: {e}")
            return False

    # ---------- Провайдер 3: NanoBanana (пример REST API) ----------
    async def _try_nanobanana(self, prompt: str, out_path: Path) -> bool:
        if not self.NANOBANANA_API_KEY:
            return False
        # Пример — замените на актуальный эндпоинт вашей интеграции
        url = "https://api.nanobanana.ai/v1/generate"
        headers = {"Authorization": f"Bearer {self.NANOBANANA_API_KEY}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "size": "1024x1024"}
        try:
            async with aiohttp.ClientSession(timeout=self.request_timeout) as session:
                async with session.post(url, json=payload, headers=headers) as r:
                    if r.status != 200:
                        return False
                    data = await r.json()
                    img_url = data.get("url")
                    if not img_url:
                        return False
                async with aiohttp.ClientSession(timeout=self.request_timeout) as session:
                    async with session.get(img_url) as ir:
                        if ir.status == 200 and ir.content_type.startswith("image/"):
                            async with aiofiles.open(out_path, "wb") as f:
                                async for chunk in ir.content.iter_chunked(8192):
                                    await f.write(chunk)
                            return True
        except Exception as e:
            print(f"⚠️ NanoBanana ошибка: {e}")
        return False

    # ---------- Координация: берем первый успешный ----------
    async def generate_image(self, situation: str, answer: Optional[str] = None, filename_stub: Optional[str] = None) -> Optional[Path]:
        # Собираем промпт
        base = situation.replace("____", answer or "неожиданный поворот")
        prompt = f"{base}, cartoon, vibrant, colorful, high quality"

        out_path = self.images_dir / f"{filename_stub or f'img_{random.randint(1000,9999)}'}.png"

        async def run_try(coro):
            try:
                return await coro
            except Exception:
                return False

        tasks = [
            run_try(self._try_pollinations(prompt, out_path)),
            run_try(self._try_horde(prompt, out_path)),
            run_try(self._try_nanobanana(prompt, out_path)),
        ]

        # ждем первый True
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        success = any(t.result() for t in done if not t.cancelled())

        # отменяем остальные
        for t in pending:
            t.cancel()

        if success and out_path.exists():
            return out_path
        return None

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        await bot.send_message(chat_id, f"🎲 Ситуация:\n\n_{situation}_", parse_mode="Markdown")
        path = await self.generate_image(situation, answer=answer)
        if path and path.exists():
            await bot.send_photo(chat_id, photo=FSInputFile(path))
            return True
        else:
            await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
            return False


# -------------------- Экспортируемые объекты --------------------

decks = DeckManager()     # Менеджер колод (situations/answers) [1][2][3]
gen = GameImageGenerator()  # Генератор изображений (без OpenAI, через внешние провайдеры) [4][5]


# -------------------- Утилиты --------------------

def get_random_situation() -> str:
    return decks.get_random_situation()

async def send_random_situation_with_image(bot: Bot, chat_id: int) -> bool:
    sit = decks.get_random_situation()
    return await gen.send_illustration(bot, chat_id, sit)
