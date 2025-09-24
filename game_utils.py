# game_utils.py

import os
import requests

# Адрес локального сервиса генерации изображений (можно задать через ENV)
IMAGE_API_URL = os.getenv("IMAGE_API_URL", "http://localhost:5000/generate")
REQUEST_TIMEOUT = float(os.getenv("IMAGE_API_TIMEOUT", 10.0))  # секунд

def generate_image_bytes(prompt: str) -> bytes:
    """
    Отправляет prompt на локальный HTTP-сервис генерации изображений и возвращает
    содержимое PNG-файла в виде байтов. В случае ошибки возвращает пустые байты.
    """
    payload = {"prompt": prompt}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            IMAGE_API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.content
    except requests.Timeout:
        print(f"Таймаут при обращении к {IMAGE_API_URL} (timeout={REQUEST_TIMEOUT}s)")
    except requests.RequestException as e:
        print(f"Ошибка при HTTP-запросе к {IMAGE_API_URL}: {e}")
    return b""
