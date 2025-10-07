# gigachat_utils.py
import os
import uuid
import requests
import re
import hashlib
import time
from typing import Optional
from dotenv import load_dotenv
import warnings

# Отключаем предупреждения SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

load_dotenv()

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")

class GigaChatImageGenerator:
    """
    Класс для генерации изображений через GigaChat + Kandinsky 3.1
    """
    
    def __init__(self):
        self.access_token = None
        self.token_expiry = 0  # Время истечения токена
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        self.files_url = "https://gigachat.devices.sberbank.ru/api/v1/files"
    
    def _get_access_token(self) -> Optional[str]:
        """
        Получение access token для GigaChat API
        
        Returns:
            Access token или None при ошибке
        """
        try:
            if not GIGACHAT_AUTH_KEY:
                print("❌ GIGACHAT_AUTH_KEY не найден в .env")
                return None
            
            headers = {
                "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",  # Используем напрямую
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "scope": "GIGACHAT_API_PERS"
            }
            
            response = requests.post(
                self.token_url,
                headers=headers,
                data=data,
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result["access_token"]
                # Сохраняем время истечения (30 минут - 1 минута запас)
                self.token_expiry = time.time() + 1740  # 29 минут
                print(f"✅ GigaChat токен получен")
                return self.access_token
            else:
                print(f"❌ Ошибка получения токена: {response.status_code}")
                print(f"   Ответ: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка GigaChat auth: {e}")
            return None
    
    def _ensure_token(self) -> bool:
        """
        Проверяет токен и обновляет при необходимости
        
        Returns:
            True если токен валиден, False при ошибке
        """
        # Если токена нет или он истек
        if not self.access_token or time.time() >= self.token_expiry:
            print("🔄 Обновление токена GigaChat...")
            return self._get_access_token() is not None
        return True
    
    def generate_image(self, prompt: str) -> Optional[str]:
        """
        Генерирует изображение через GigaChat + Kandinsky 3.1
        
        Args:
            prompt: Описание изображения на русском языке
            
        Returns:
            Путь к сохраненному изображению или None при ошибке
        """
        try:
            # Проверяем/обновляем токен
            if not self._ensure_token():
                return None
            
            print(f"🎨 Генерация изображения через GigaChat + Kandinsky...")
            
            # Формируем запрос для генерации изображения
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "GigaChat",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Нарисуй изображение: {prompt}"
                    }
                ],
                "function_call": "auto"
            }
            
            # Отправляем запрос
            response = requests.post(
                self.chat_url,
                headers=headers,
                json=data,
                verify=False,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"⚠️ GigaChat вернул ошибку: {response.status_code}")
                print(f"   Ответ: {response.text}")
                return None
            
            result = response.json()
            
            # Извлекаем file_id изображения
            content = result["choices"][0]["message"]["content"]
            
            # Ищем file_id в ответе (формат: <img src="file_id"/>)
            file_id_match = re.search(r'<img src="([^"]+)"', content)
            
            if not file_id_match:
                print("⚠️ GigaChat не вернул изображение")
                print(f"   Ответ: {content}")
                return None
            
            file_id = file_id_match.group(1)
            print(f"📎 Получен file_id: {file_id}")
            
            # Скачиваем изображение
            image_url = f"{self.files_url}/{file_id}/content"
            image_response = requests.get(
                image_url,
                headers=headers,
                verify=False,
                timeout=30
            )
            
            if image_response.status_code == 200:
                # Сохраняем изображение
                file_hash = hashlib.md5(prompt.encode()).hexdigest()[:10]
                temp_path = f"temp_gigachat_{file_hash}.jpg"
                
                with open(temp_path, 'wb') as f:
                    f.write(image_response.content)
                
                print(f"✅ GigaChat изображение сохранено: {temp_path}")
                return temp_path
            else:
                print(f"⚠️ Ошибка скачивания изображения: {image_response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка GigaChat генерации: {e}")
            import traceback
            traceback.print_exc()
            return None

# КРИТИЧЕСКИ ВАЖНО: создаем глобальный экземпляр для импорта
gigachat_generator = GigaChatImageGenerator()
