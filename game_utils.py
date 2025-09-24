# game_utils.py

import requests

# Адрес локального сервиса генерации изображений
IMAGE_API_URL = "http://localhost:5000/generate"

def generate_image_bytes(prompt: str) -> bytes:
    """
    Посылает prompt на локальный HTTP-сервис и возвращает
    байты PNG-изображения.
    """
    try:
        response = requests.post(IMAGE_API_URL, json={"prompt": prompt})
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Ошибка при вызове сервиса генерации: {e}")
        return b""
