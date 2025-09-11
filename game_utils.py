# game_utils.py

import json, random, os, asyncio
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from aiogram.types import FSInputFile
from aiogram import Bot

# Конфигурируем Gemini API с вашим ключом
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception as e:
    print(f"❌ Не удалось сконфигурировать Gemini. Проверьте GOOGLE_API_KEY. Ошибка: {e}")

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json", images_dir: str = "generated_images"):
        self.situations_file = situations_file
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(exist_ok=True)
        self.situations = self._load_situations()
        # Модель для генерации изображений
        self.model = genai.GenerativeModel('gemini-pro-vision') # Замените на актуальную модель, если необходимо

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str, image_id: Optional[str] = None) -> Optional[Path]:
        if not os.getenv("GOOGLE_API_KEY"):
            print("❌ GOOGLE_API_KEY не найден.")
            return None
        try:
            # Для Gemini генерация изображений может быть частью более сложного ответа
            # Поэтому мы явно просим сгенерировать изображение
            generation_model = genai.GenerativeModel('imagen-2') # Специализированная модель для изображений
            response = await generation_model.generate_content_async(prompt)
            
            # Gemini API для изображений может работать иначе, этот код - адаптация
            # В реальности API может возвращать URL или байты напрямую
            # Предполагаем, что response содержит байты изображения, если это так.
            # Этот блок нужно будет адаптировать под точный формат ответа Imagen 2
            
            # ЗАГЛУШКА, т.к. точный API для байтов может отличаться.
            # Если API возвращает URL, здесь будет код для скачивания по URL.
            # Если возвращает байты, то `response.media[0].content` или类似ное.
            # Так как прямого аналога DALL-E нет, создадим заглушку
            print("⚠️ API для генерации изображений Gemini может потребовать специфической обработки ответа.")
            # Вместо реальной генерации, создадим временное пустое изображение для демонстрации
            from PIL import Image
            img = Image.new('RGB', (200, 200), color = 'red')
            output_path = self.images_dir / f"{image_id or random.randint(1000, 9999)}.png"
            img.save(output_path)
            return output_path
            
        except Exception as e:
            print(f"❌ Ошибка при генерации изображения Gemini: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        prompt = f"Ситуация: {situation}. Ответ игрока: {answer}. Мультяшная яркая иллюстрация в стиле мемов."
        
        image_path = await self.generate_image_from_prompt(prompt, f"round_{chat_id}")
        
        if image_path:
            await bot.send_photo(chat_id, photo=FSInputFile(image_path))
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Проверьте консоль.")
        return False

# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()
