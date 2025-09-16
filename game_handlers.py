import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from typing import Dict, Any

router = Router()

SESSIONS: Dict[int, Dict] = {}

API_KEY = "key_1f8f897a63cd034fa49950b4c4cea0db6b4ae30708b4cbe9674bd1cb9cad71f5893fa54613a1feaa797081e6ff1fd5f9801a5d00a6b611e321c24bfe3344d01c"  # Поставьте сюда ваш ключ RunwayML

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

async def generate_runway_video_from_text(api_key: str, prompt_text: str) -> str | None:
    url = "https://api.runwayml.com/v1/text_to_video"  # Проверьте актуальный endpoint в документации RunwayML

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gen4_turbo",
        "promptText": prompt_text,
        "ratio": "16:9"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                video_url = data.get("videoUrl") or data.get("video_url")
                return video_url
            else:
                error_text = await response.text()
                print(f"RunwayML API error {response.status}: {error_text}")
                return None

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню.", reply_markup=main_menu())

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    SESSIONS[cb.message.chat.id] = {
        "players": [],
        "answers": {},
        "host_idx": -1,
        "current_situation": None,
    }
    await cb.answer()
    try:
        await cb.message.edit_text("✅ Игра начата!", reply_markup=main_menu())
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "ui_join_game")
async def ui_join_game(cb: CallbackQuery):
    st = SESSIONS.get(cb.message.chat.id)
    if not st:
        await cb.answer("Игра не начата, нажмите 'Начать игру'.", show_alert=True)
        return
    if cb.from_user.id not in st["players"]:
        st["players"].append(cb.from_user.id)
    await cb.answer(f"Вы присоединились! Игроков: {len(st['players'])}")

@router.callback_query(F.data == "ui_start_round")
async def ui_start_round(cb: CallbackQuery):
    st = SESSIONS.get(cb.message.chat.id)
    if not st or len(st["players"]) < 2:
        await cb.answer("Нужно минимум 2 игрока.", show_alert=True)
        return
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    st["current_situation"] = "Пример ситуации для генерации видео"  # Замените на реальную ситуацию
    # Для простоты возьмём ответ последнего присоединившегося игрока
    answer = "Пример ответа победителя"
    await cb.answer()
    prompt_text = f"Ситуация: {st['current_situation']}. Ответ: {answer}. Анимация, выразительный стиль, качественный видеоклип."
    video_url = await generate_runway_video_from_text(API_KEY, prompt_text)
    if video_url:
        await cb.message.answer("Смотрите сгенерированное видео:")
        await cb.bot.send_video(cb.message.chat.id, video=video_url)
    else:
        await cb.message.answer("Не удалось сгенерировать видео.")

# Остальной код игры (обработка ответов, выбор победителя) добавляйте по необходимости и интегрируйте вызов генерации видео аналогично выше

