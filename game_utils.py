# game_utils.py — Полностью обновлённый с create_prompt, _load_list и send_illustration без подписи
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
    """Создает детальный промпт для фотореалистичных изображений с автопереводом."""
    
    def translate_to_english(text: str) -> str:
        """Переводит текст на английский если содержит кириллицу."""
        if any(ord(c) > 127 for c in text):  # есть русские символы
            try:
                from googletrans import Translator
                translator = Translator()
                result = translator.translate(text, dest='en').text
                return result
            except Exception as e:
                print(f"⚠️ Ошибка перевода: {e}")
                return text  # возвращаем оригинал если перевод не удался
        return text
    
    # Очищаем ситуацию от пропусков
    situation_clean = situation.replace("_____", "").replace("____", "").strip()
    
    # Переводим на английский
    situation_en = translate_to_english(situation_clean)
    answer_en = translate_to_english(answer.strip())
    
    # Определяем обстановку для сцены
    situation_lower = situation.lower()
    if "утр" in situation_lower or "morning" in situation_en.lower():
        scene_setting = "morning scene with natural sunlight"
    elif "вечер" in situation_lower or "evening" in situation_en.lower():
        scene_setting = "evening indoor scene with warm lighting"
    elif "работ" in situation_lower or "офис" in situation_lower or "work" in situation_en.lower():
        scene_setting = "office environment"
    elif "дом" in situation_lower or "home" in situation_en.lower():
        scene_setting = "cozy home interior"
    elif "кухн" in situation_lower or "kitchen" in situation_en.lower():
        scene_setting = "modern kitchen setting"
    else:
        scene_setting = "realistic everyday scene"
    
    # Создаём описание сцены
    scene_description = f"Professional photograph of {answer_en} in {scene_setting}, related to: {situation_en}"
    
    # Стилевые модификаторы для фотореализма
    style_modifiers = [
        "photorealistic",
        "high quality photography", 
        "professional lighting",
        "sharp focus",
        "natural colors",
        "realistic details",
        "documentary style",
        "authentic moment",
        "clear composition",
        "lifelike textures"
    ]
    
    # Финальный промпт
    final_prompt = f"{scene_description}, {', '.join(style_modifiers)}"
    
    # Отладочный вывод
    print(f"📝 [Ситуация] {situation}")
    print(f"📝 [Ответ] {answer}")
    print(f"📝 [Перевод ситуации] {situation_en}")
    print(f"📝 [Перевод ответа] {answer_en}")
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
