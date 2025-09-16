# game_utils/gen.py — иллюстрация (заглушка) + генерация видео через Runway
import os
import asyncio
import aiohttp
from aiogram import Bot

RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
RUNWAY_BASE = "https://api.runwayml.com/v1"

async def send_illustration(bot: Bot, chat_id: int, situation: str, answer: str) -> str | None:
    """
    ВАША текущая генерация изображения.
    Здесь заглушка: отправляет текст и возвращает None.
    Если у вас уже есть реальная генерация (например, через SD/Replicate),
    верните публичный URL картинки — он пойдёт как reference_image_url в видео.
    """
    await bot.send_message(chat_id, f"🖼️ Иллюстрация: {situation}\n— {answer}")
    return None  # верните URL, если он у вас есть

async def _runway_create_task(session: aiohttp.ClientSession, payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
    }
    async with session.post(f"{RUNWAY_BASE}/tasks", json=payload, headers=headers) as resp:
        if resp.status >= 400:
            text = await resp.text()
            raise RuntimeError(f"Runway create failed {resp.status}: {text}")
        return await resp.json()

async def _runway_get_task(session: aiohttp.ClientSession, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}"}
    async with session.get(f"{RUNWAY_BASE}/tasks/{task_id}", headers=headers) as resp:
        if resp.status >= 400:
            text = await resp.text()
            raise RuntimeError(f"Runway get failed {resp.status}: {text}")
        return await resp.json()

async def send_runway_video(
    bot: Bot,
    chat_id: int,
    situation: str,
    answer: str,
    reference_image_url: str | None = None,
    duration: int = 5,
    model: str = "gen_4_turbo",
):
    """
    Создаёт видео по ситуации и победившему ответу через Runway API и отправляет в чат.
    Использует image-to-video при наличии reference_image_url, иначе text-to-video.
    """
    if not RUNWAY_API_KEY:
        await bot.send_message(chat_id, "⚠️ RUNWAY_API_KEY не задан в окружении.")
        return

    # Формируем промпт
    prompt = f"{situation}. Then: {answer}. Cinematic camera, smooth motion, realistic lighting."

    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "duration": duration,
        }
    }
    if reference_image_url:
        payload["input"]["image"] = reference_image_url  # image-to-video режим

    # Сообщение о старте
    await bot.send_message(chat_id, "🎥 Генерация видео в Runway… подождите 30–90 секунд.")

    try:
        timeout = aiohttp.ClientTimeout(total=900)  # до 15 минут на всякий случай
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 1) создаём задачу
            task = await _runway_create_task(session, payload)
            task_id = task.get("id")

            if not task_id:
                await bot.send_message(chat_id, "❌ Не удалось создать задачу в Runway (пустой task_id).")
                return

            # 2) опрос статуса
            attempts = 0
            while True:
                await asyncio.sleep(2)
                attempts += 1
                data = await _runway_get_task(session, task_id)
                status = data.get("status")
                if status in ("SUCCEEDED", "FAILED", "CANCELED", "THROTTLED"):
                    if status == "SUCCEEDED":
                        output = data.get("output", {}) or {}
                        # По докам результат — URL(ы), иногда ключ называется video/url
                        video_url = (
                            output.get("video")
                            or output.get("output_video")
                            or output.get("url")
                        )
                        if not video_url:
                            await bot.send_message(chat_id, "⚠️ Видео готово, но ссылка не найдена.")
                            return
                        # 3) отправляем как видео
                        await bot.send_video(chat_id, video=video_url, caption="🎬 Runway видео по победившему ответу")
                        return
                    elif status == "THROTTLED":
                        # перегрузка по concurrency — просто подождать дольше
                        await bot.send_message(chat_id, "⏳ Очередь Runway занята (THROTTLED). Ждём…")
                        # и продолжаем polling
                    else:
                        err = data.get("error") or "Неизвестная ошибка"
                        await bot.send_message(chat_id, f"❌ Runway ошибка: {err}")
                        return

                # таймаут ожидания
                if attempts > 600:  # ~20 минут
                    await bot.send_message(chat_id, "⏱️ Таймаут ожидания ответа от Runway.")
                    return

    except Exception as e:
        await bot.send_message(chat_id, f"❌ Ошибка при обращении к Runway: {e}")
