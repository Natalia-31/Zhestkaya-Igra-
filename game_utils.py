# game_utils.py — Полностью обновлённый с улучшенной функцией create_prompt для мультяшных изображений

import os
import json
import random
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# ========== Загрузка ключей ==========
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# ========== Функция для создания промпта ==========
def create_prompt(situation: str, answer: str) -> str:
    """Создает промпт для мультяшных изображений с контекстом."""
    
    def translate_to_english(text: str) -> str:
        """Переводит текст на английский если содержит кириллицу."""
        if any(ord(c) > 127 for c in text):
            try:
                from googletrans import Translator
                translator = Translator()
                result = translator.translate(text, dest='en').text
                return result
            except Exception as e:
                print(f"⚠️ Ошибка перевода: {e}")
                return text
        return text
    
    # Переводим
    situation_clean = situation.replace("_____", "").replace("____", "").strip()
    situation_en = translate_to_english(situation_clean)
    answer_en = translate_to_english(answer.strip())
    
    # Короткое контекстное описание: ситуация + ответ
    context_description = f"{situation_en} - {answer_en}"
    
    # Стили для выбора
    styles = ["cartoon", "caricature", "comic panel", "flat colors"]
    chosen_style = random.choice(styles)
    
    # Ракурсы/перспективы
    perspectives = ["wide shot", "close-up", "medium shot", "bird's eye view", "low angle"]
    chosen_perspective = random.choice(perspectives)
    
    # Эмоции
    emotions = ["amused expression", "surprised look", "confused face", "happy smile", "shocked expression", "thoughtful pose"]
    chosen_emotion = random.choice(emotions)
    
    # Собираем финальный промпт
    final_prompt = f"{context_description}, {chosen_style}, {chosen_perspective}, {chosen_emotion}, colorful, simple shapes, expressive"
    
    # Отладочный вывод
    print(f"📝 [Ситуация] {situation}")
    print(f"📝 [Ответ] {answer}")
    print(f"📝 [Контекст] {context_description}")
    print(f"📝 [Стиль] {chosen_style}")
    print(f"📝 [Ракурс] {chosen_perspective}")
    print(f"📝 [Эмоция] {chosen_emotion}")
    print(f"📝 [Финальный промпт] {final_prompt}")
    
    return final_prompt

# ========== Менеджер колод ==========
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        # Выводим для отладки, существует ли файл и где он
        print(f"🔍 Loading '{label}' from {file_path} (exists={file_path.exists()})")
        for enc in ("utf-8-sig", "utf-8"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc}): {len(data)} items")
                    return data
                else:
                    print(f"⚠️ {file_path} ({label}) не содержит JSON-список")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path}")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Кодировка {enc} не подошла: {e}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON ошибка ({enc}) в {file_path}: {e}")
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка ({enc}) при чтении {file_path}: {e}")
        print(f"⚠️ Не удалось загрузить '{label}' из {file_path} ни с одной кодировкой")
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Если бы не ____, я бы бросил пить."

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck

decks = DeckManager()

# ========== Генератор изображений ==========
class GameImageGenerator:
    def __init__(self):
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=15) as r:
                    if r.status == 200:
                        return BytesIO(await r.read())
        except:
            pass
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            return None
        payload = {
            "prompt": prompt,
            "model": "sdxl",
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg_scale": 7.0
        }
        headers = {"Authorization": f"Bearer {self.nb_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(self.nb_url, json=payload, headers=headers, timeout=40) as r:
                    if r.status == 200:
                        data = await r.json()
                        img_url = data.get("image_url")
                        if img_url:
                            async with s.get(img_url, timeout=20) as ir:
                                if ir.status == 200:
                                    return BytesIO(await ir.read())
        except:
            pass
        return None

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False

        prompt = create_prompt(situation, answer)
        tasks = [
            self._try_pollinations(prompt),
            self._try_nanobanana(prompt),
        ]
        for future in asyncio.as_completed(tasks):
            try:
                img_buf = await future
                if img_buf:
                    await bot.send_photo(
                        chat_id,
                        photo=BufferedInputFile(file=img_buf.read(), filename="game_scene.jpg")
                    )
                    return True
            except:
                continue

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение по вашей ситуации.")
        return False

gen = GameImageGenerator()
