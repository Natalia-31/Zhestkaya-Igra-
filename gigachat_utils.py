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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        self.token_expiry = 0
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        self.files_url = "https://gigachat.devices.sberbank.ru/api/v1/files"
        
        # Создаем session с retry-механизмом
        self.session = self._create_retry_session()
    
    def _create_retry_session(self, retries=3, backoff_factor=1.0):
        """
        Создает сессию с автоматическими повторными попытками
        
        Args:
            retries: Количество попыток (по умолчанию 3)
            backoff_factor: Множитель задержки между попытками
            
        Returns:
            Настроенная сессия requests
        """
        session = requests.Session()
        
        retry_strategy = Retry(
            total=retries,  # Всего попыток
            backoff_factor=backoff_factor,  # Задержка: 1, 2, 4 секунды
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP коды для retry
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
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
                "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "scope": "GIGACHAT_API_PERS"
            }
            
            response = self.session.post(
                self.token_url,
                headers=headers,
                data=data,
                verify=False,
                timeout=(10, 15)  # (connect timeout, read timeout)
            )
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result["access_token"]
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
        if not self.access_token or time.time() >= self.token_expiry:
            print("🔄 Обновление токена GigaChat...")
            return self._get_access_token() is not None
        return True
    
    def generate_image(self, prompt: str, max_attempts=2) -> Optional[str]:
        """
        Генерирует изображение через GigaChat + Kandinsky 3.1
        
        Args:
            prompt: Описание изображения на русском языке
            max_attempts: Максимальное количество попыток
            
        Returns:
            Путь к сохраненному изображению или None при ошибке
        """
        for attempt in range(max_attempts):
            try:
                # Проверяем/обновляем токен
                if not self._ensure_token():
                    return None
                
                print(f"🎨 Генерация изображения через GigaChat + Kandinsky (попытка {attempt + 1}/{max_attempts})...")
                
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
                
                # Отправляем запрос с увеличенным timeout
                # Генерация изображений может занимать 60+ секунд
                response = self.session.post(
                    self.chat_url,
                    headers=headers,
                    json=data,
                    verify=False,
                    timeout=(15, 90)  # connect: 15s, read: 90s для генерации изображений
                )
                
                if response.status_code != 200:
                    print(f"⚠️ GigaChat вернул ошибку: {response.status_code}")
                    print(f"   Ответ: {response.text}")
                    
                    # Если это последняя попытка, возвращаем None
                    if attempt == max_attempts - 1:
                        return None
                    
                    # Иначе ждем и пробуем снова
                    print(f"   Ожидание {(attempt + 1) * 3} секунд перед повтором...")
                    time.sleep((attempt + 1) * 3)
                    continue
                
                result = response.json()
                
                # Извлекаем file_id изображения
                content = result["choices"][0]["message"]["content"]
                
                # Ищем file_id в ответе (формат: <img src="file_id"/>)
                file_id_match = re.search(r'<img src="([^"]+)"', content)
                
                if not file_id_match:
                    print("⚠️ GigaChat не вернул изображение")
                    print(f"   Ответ: {content}")
                    
                    if attempt == max_attempts - 1:
                        return None
                    
                    time.sleep((attempt + 1) * 3)
                    continue
                
                file_id = file_id_match.group(1)
                print(f"📎 Получен file_id: {file_id}")
                
                # Скачиваем изображение
                image_url = f"{self.files_url}/{file_id}/content"
                image_response = self.session.get(
                    image_url,
                    headers=headers,
                    verify=False,
                    timeout=(10, 30)
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
                    
                    if attempt == max_attempts - 1:
                        return None
                    
                    time.sleep((attempt + 1) * 3)
                    continue
                    
            except requests.exceptions.ReadTimeout:
                print(f"⏱️ Timeout на попытке {attempt + 1}/{max_attempts}")
                if attempt == max_attempts - 1:
                    print("❌ GigaChat: Превышено время ожидания после всех попыток")
                    return None
                print(f"   Повторная попытка через {(attempt + 1) * 5} секунд...")
                time.sleep((attempt + 1) * 5)
                
            except Exception as e:
                print(f"❌ Ошибка GigaChat генерации: {e}")
                if attempt == max_attempts - 1:
                    import traceback
                    traceback.print_exc()
                    return None
                time.sleep((attempt + 1) * 3)
        
        return None

# КРИТИЧЕСКИ ВАЖНО: создаем глобальный экземпляр для импорта
gigachat_generator = GigaChatImageGenerator()
