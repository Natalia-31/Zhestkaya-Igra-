from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

import openai
from config import OPENAI_SETTINGS, OPENAI_API_KEY

from game_utils import decks, video_gen

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}


async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    host = st.get("host")

    # Генерация ситуации через OpenAI
    openai.api_key = OPENAI_API_KEY
    ai_resp = await openai.ChatCompletion.acreate(
        model=OPENAI_SETTINGS["MODEL"],
        messages=[{"role": "system", "content": "Придумай забавную ситуацию для карточной игры."}],
        max_tokens=OPENAI_SETTINGS["MAX_TOKENS"],
        temperature=OPENAI_SETTINGS["TEMPERATURE"],
    )
    st["current_situation"] = ai_resp.choices[0].message.content.strip()

    await bot.send_message(
        chat_id,
        f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {st['current_situation']}"
    )


@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    data = cb.data.split(":")
    group_chat_id = int(data[1])
    winner_id = int(data[2])

    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("⚠️ Раунд не найден.")
        return

    win_ans = st["answers"].get(winner_id)
    if not win_ans:
        await cb.answer("⚠️ Ответ не найден.")
        return

    try:
        # Опционально: иллюстрация через OpenAI
        openai.api_key = OPENAI_API_KEY
        img_resp = await openai.Image.acreate(
            prompt=f"{st['current_situation']} {win_ans}",
            n=1,
            size="512x512"
        )
        image_url = img_resp.data[0].url

        await video_gen.send_video_illustration(
            cb.bot,
            group_chat_id,
            st["current_situation"],
            win_ans,
            image_url  # если у тебя видео_ген поддерживает ещё и картинку
        )
    except Exception as e:
        await cb.bot.send_message(group_chat_id, f"⚠️ Не удалось сгенерировать видео: {e}")
