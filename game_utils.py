# game_utils.py - ФИНАЛЬНАЯ ВЕРСИЯ С ОПТИМИЗИРОВАННЫМИ ПРОМПТАМИ

import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from aiogram import Bot
from aiogram.types import BufferedInputFile


def create_pollinations_prompt(situation: str, answer: str) -> str:
    """
    Создает оптимизированный промпт для Pollinations.ai
    """
    # Убираем прочерки и объединяем ситуацию с ответом
    combined_text = situation.replace("____", answer).strip()
    
    # Словарь для быстрого перевода частых фраз
    quick_translations = {
        "На вечеринке": "at a party",
        "в ресторане": "in a restaurant", 
        "дома": "at home",
        "на работе": "at work",
        "в магазине": "in a store",
        "на улице": "on the street",
        "в школе": "at school",
        "в университете": "at university",
        "в театре": "at theater",
        "в кино": "at cinema",
        "Мой секретный талант": "My secret talent is",
        "Самая странная причина": "The strangest reason",
        "Самая распространенная причина": "The most common reason",
        "опоздать": "to be late",
        "проснуться": "to wake up",
        "засмеяться": "everyone laughing",
        "упасть": "falling",
        "танцевать": "dancing",
        "петь": "singing",
        "кричать": "shouting",
        "плакать": "crying",
        "смеяться": "laughing",
        "бежать": "running",
        "прыгать": "jumping",
        "холодильник": "refrigerator",
        "кот в сапогах": "puss in boots",
        "собака": "dog",
        "кот": "cat",
        "птица": "bird"
    }
    
    # Применяем быстрые переводы
    english_text = combined_text
    for ru_phrase, en_phrase in quick_translations.items():
        english_text = english_text.replace(ru_phrase, en_phrase)
    
    # Если остались русские слова, применяем полный перевод
    if any(ord(char) > 127 for char in english_text):  # Проверка на кириллицу
        try:
            from googletrans import Translator
            translator = Translator()
            translation = translator.translate(combined_text, dest='en')
            english_text = translation.text
        except Exception as e:
            print(f"❌ Ошибка перевода: {e}. Используем частичный перевод.")
            # Fallback: оставляем как есть с частичными переводами
    
    # Формируем финальный промпт по оптимизированному шаблону
    style_modifiers = "photorealistic cinematic lighting ultra detailed 8k trending on Artstation"
    
    # Создаем описательную структуру
    final_prompt = f"A photorealistic cinematic photo of {english_text}, {style_modifiers}"
    
    # Очищаем промпт от лишних символов и дублирований
    final_prompt = final_prompt.replace(",,", ",").replace("..", ".").replace("  ", " ").strip()
    
    return final_prompt


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()

    def _load_situations(self) -> list:
        """
        Загружает ситуации из JSON-файла.
        """
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        # Резервный список на случай, если файл не найден или пуст
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____.",
            "В ресторане я случайно ____.",
            "На работе меня застали за ____.",
            "Дома я обнаружил, что мой холодильник ____."
        ]

    def get_random_situation(self) -> str:
        """
        Возвращает случайную ситуацию из списка.
        """
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через URL-запрос к Pollinations.ai.
        """
        encoded_prompt = quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024"
        
        print(f"🤖 Запрашиваю изображение по URL: {image_url}")

        try:
            # Асинхронно скачиваем изображение
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        print("✅ Изображение успешно получено.")
                        return BytesIO(image_bytes)
                    else:
                        print(f"❌ Ошибка от сервера Pollinations: статус {resp.status}")
                        return None
        except Exception as e:
            print(f"❌ Ошибка при скачивании изображения: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        """
        Собирает оптимизированный промпт из ситуации и ответа, генерирует и отправляет изображение.
        """
        if answer:
            # Используем новую функцию для создания оптимизированного промпта
            prompt = create_pollinations_prompt(situation, answer)
        else:
            # Резервный вариант, если ответа нет
            prompt = f"A photorealistic cinematic photo of {situation}, ultra detailed, 8k"

        # Получаем сгенерированное изображение в виде байтов
        image_bytes_io = await self.generate_image_from_prompt(prompt)

        if image_bytes_io:
            # Отправляем фото в чат
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
                caption=f"🎨 Промпт: {prompt}"  # Добавил эмодзи для красоты
            )
            return True

        # Если что-то пошло не так, отправляем сообщение об ошибке
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
        return False


# Глобальный экземпляр класса, который используется в других файлах
gen = GameImageGenerator()

# Вспомогательная функция, чтобы другие файлы могли легко получить ситуацию
def get_random_situation() -> str:
    return gen.get_random_situation()
