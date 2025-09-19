import httpx
import base64
from aiogram.types import BufferedInputFile

import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def generate_image_gemini(prompt: str) -> bytes:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=headers, timeout=70)
        resp.raise_for_status()
        result = resp.json()
        # Проверьте реальный ответ Gemini! Если путь не сработает — print(result)
        image_base64 = result['candidates'][0]['content']['parts'][0]['inline_data']['data']
        return base64.b64decode(image_base64)

async def send_image_illustration(bot, chat_id: int, situation: str, answer: str):
    prompt = f"Ситуация: {situation}. Ответ игрока: {answer}."
    image_bytes = await generate_image_gemini(prompt)
    await bot.send_photo(chat_id, BufferedInputFile(image_bytes, filename="gemini.png"),
                        caption=f"AI иллюстрация:\nСитуация: <i>{situation}</i>\nОтвет: <b>{answer}</b>",
                        parse_mode="HTML")
