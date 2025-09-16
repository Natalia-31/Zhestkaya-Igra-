# game_utils.py — Полностью обновлённый с видеогенерацией через Pollo.ai

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
POLLO_API_KEY = os.getenv("POLLO_API_KEY")

# ========== Функции для создания промптов ==========
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

def create_video_prompt(situation: str, answer: str) -> str:
    """Создаёт промпт для видеогенерации."""
    
    def translate_to_english(text: str) -> str:
        if any(ord(c) > 127 for c in text):
            try:
                from googletrans import Translator
                return Translator().translate(text, dest='en').text
            except:
                return text
        return text
    
    # Переводим
    situation_clean = situation.replace("_____", "").replace("____", "").strip()
    situation_en = translate_to_english(situation_clean)
    answer_en = translate_to_english(answer.strip())
    
    # Сценарии движения для видео
    motion_scenarios = [
        f"Person interacting with {answer_en} while thinking about: {situation_en}",
        f"Dynamic scene showing {answer_en} in action, representing: {situation_en}",
        f"Animated sequence of {answer_en} responding to: {situation_en}",
        f"Character discovering {answer_en} in context of: {situation_en}",
        f"Humorous scene with {answer_en} solving problem: {situation_en}"
    ]
    
    chosen_scenario = random.choice(motion_scenarios)
    
    # Стили движения
    motion_styles = ["smooth animation", "bouncy movement", "dramatic zoom", "gentle pan", "dynamic rotation"]
    chosen_motion = random.choice(motion_styles)
    
    # Создаём видео-промпт
    video_prompt = f"6-second cartoon video: {chosen_scenario}, {chosen_motion}, colorful, expressive characters, simple animation style"
    
    print(f"🎬 [Видео промпт] {video_prompt}")
    return video_prompt

# ========== Менеджер колод ==========
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
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

# ========== Генератор видео через Pollo.ai ==========
class GameVideoGenerator:
    def __init__(self):
        self.pollo_key = POLLO_API_KEY
        self.pollo_url = "https://pollo.ai/api/platform/generation/minimax/video-01"
        
    async def _try_pollo_video(self, prompt: str) -> Optional[str]:
        """Генерирует видео через Pollo.ai API."""
        if not self.pollo_key:
            print("⚠️ Pollo API key не найден в .env файле")
            return None
            
        try:
            payload = {
                "input": {
                    "prompt": prompt
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.pollo_key
            }
            
            print(f"🎬 Отправляем запрос на генерацию видео...")
            
            async with aiohttp.ClientSession() as session:
                # Запрос на генерацию
                async with session.post(self.pollo_url, json=payload, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        task_id = data.get("taskId")
                        print(f"📝 Задача создана: {task_id}")
                        
                        if not task_id:
                            print("❌ Не получен ID задачи")
                            return None
                        
                        # Ждём завершения генерации
                        for attempt in range(30):  # 5 минут ожидания (30 * 10 секунд)
                            await asyncio.sleep(10)
                            status_url = f"https://pollo.ai/api/platform/generation/{task_id}"
                            
                            async with session.get(status_url, headers=headers, timeout=30) as status_response:
                                if status_response.status == 200:
                                    status_data = await status_response.json()
                                    status = status_data.get("status")
                                    print(f"📊 Статус ({attempt + 1}/30): {status}")
                                    
                                    if status == "completed":
                                        video_url = status_data.get("output", {}).get("url")
                                        print(f"✅ Видео готово: {video_url}")
                                        return video_url
                                    elif status == "failed":
                                        print("❌ Генерация видео не удалась")
                                        return None
                                else:
                                    print(f"⚠️ Ошибка статуса: {status_response.status}")
                        
                        print("⏰ Превышено время ожидания генерации")
                    else:
                        error_text = await response.text()
                        print(f"❌ Ошибка запроса: {response.status} - {error_text}")
                        
        except Exception as e:
            print(f"❌ Ошибка Pollo: {e}")
        return None
    
    async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
        """Отправляет видео-иллюстрацию."""
        print(f"🎬 Начинаем генерацию видео для: {answer}")
        
        # Создаём промпт для видео
        video_prompt = create_video_prompt(situation, answer)
        
        # Генерируем видео
        video_url = await self._try_pollo_video(video_prompt)
        
        if video_url:
            try:
                print(f"📥 Скачиваем видео: {video_url}")
                # Скачиваем и отправляем видео
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url, timeout=120) as response:
                        if response.status == 200:
                            video_data = await response.read()
                            print(f"📤 Отправляем видео в чат {chat_id}")
                            
                            await bot.send_video(
                                chat_id,
                                video=BufferedInputFile(file=video_data, filename="game_video.mp4"),
                                caption=f"🎬 {answer}",
                                duration=6,
                                width=1024,
                                height=1024
                            )
                            print(f"✅ Видео отправлено успешно")
                            return True
                        else:
                            print(f"❌ Ошибка скачивания видео: {response.status}")
            except Exception as e:
                print(f"❌ Ошибка отправки видео: {e}")
        
        print("⚠️ Не удалось сгенерировать или отправить видео")
        return False

# ========== Создаём экземпляры ==========
gen = GameImageGenerator()
video_gen = GameVideoGenerator()
