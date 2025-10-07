# gigachat_utils.py
import os
import base64
import uuid
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

class GigaChatImageGenerator:
    def __init__(self):
        self.access_token = None
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        self.files_url = "https://gigachat.devices.sberbank.ru/api/v1/files"
    
    def _get_access_token(self) -> str:
        """Получение access token для GigaChat API"""
        try:
            # Создаем Basic Auth токен
            credentials = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
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
                verify=False  # Отключаем проверку SSL (нужно для GigaChat)
            )
            
            if response.status_code == 200:
                self.access_token = response.json()["access_token"]
                print(f"✅ GigaChat токен получен")
                return self.access_token
            else:
                print(f"❌ Ошибка получения токена: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка GigaChat auth: {e}")
            return None
    
    def generate_image(self, prompt: str) -> Optional[str]:
        """
        Генерирует изображение через GigaChat + Kandinsky
        
        Args:
            prompt: Описание изображения на русском
            
        Returns:
            Путь к сохраненному изображению или None
        """
        try:
            # Получаем токен если его нет
            if not self.access_token:
                if not self._get_access_token():
                    return None
            
            print(f"🎨 Генерация изображения через GigaChat...")
            
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
                return None
            
            result = response.json()
            
            # Извлекаем file_id изображения
            content = result["choices"][0]["message"]["content"]
            
            # Ищем file_id в ответе (формат: <img src="file_id"/>)
            import re
            file_id_match = re.search(r'<img src="([^"]+)"', content)
            
            if not file_id_match:
                print("⚠️ GigaChat не вернул изображение")
                return None
            
            file_id = file_id_match.group(1)
            
            # Скачиваем изображение
            image_url = f"{self.files_url}/{file_id}/content"
            image_response = requests.get(
                image_url,
                headers=headers,
                verify=False
            )
            
            if image_response.status_code == 200:
                # Сохраняем изображение
                import hashlib
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
            return None

# Создаем глобальный экземпляр
gigachat_generator = GigaChatImageGenerator()
