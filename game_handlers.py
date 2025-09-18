from typing import Dict, Any
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from PIL import Image, ImageDraw, ImageFont
from gen import format_error, format_info, log_event
from game_utils import decks, video_gen

logging.basicConfig(
    filename="game_events.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}

def format_header(text: str, style: str = "main") -> str:
    styles = {
        "main": f"🔥 ═══ {text.upper()} ═══ 🔥",
        "round": f"⚡ ┃ {text} ┃ ⚡",
        "result": f"🏆 ▸ {text} ◂ 🏆",
        "warning": f"⚠️ {text} ⚠️"
    }
    return styles.get(style, text)

def format_situation_card(situation: str, round_num: int) -> str:
    return (
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🎭 СИТУАЦИЯ #{round_num:<2}     ┃\n"
        f"┣━━━━━━━━━━━━━━━━━━━━┫\n"
        f"┃ {situation[:40]:<38} ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )

def format_countdown_timer(seconds: int) -> str:
    if seconds > 10:
        return f"⏱️ {seconds} сек"
    elif seconds > 5:
        return f"⚠️ {seconds} сек"
    else:
        return f"🔥 {seconds} сек!"

def render_scores_ascii(st: Dict[str, Any]) -> str:
    scores = st.setdefault("scores", {p["username"]: 0 for p in st["players"]})
    max_score = max(scores.values(), default=1)
    lines = ["📊 Прогресс раунда:"]
    for name, score in scores.items():
        bar = "█" * int((score / max_score) * 10)
        lines.append(f"{name:<10} |{bar:<10}| {score}")
    return "\n".join(lines)

async def send_gray_card(chat_id: int, text: str, bot: Bot, filename: str = "card.png"):
    img = Image.new("RGB", (600, 300), (230, 230, 230))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 20)
    draw.multiline_text((20, 20), text, fill=(50, 50, 50), font=font, spacing=4)
    img.save(filename)
    await bot.send_photo(chat_id, photo=InputFile(filename))

def menu_initial() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")]
    ])

def menu_joinable() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")]
    ])

def menu_for_host() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")]
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(format_info(format_header("Жесткая Игра")), reply_markup=menu_initial())

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    host_id = cb.from_user.id
    host_name = cb.from_user.full_name
    await _create_game(chat_id, host_id, host_name)
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(format_info("Игра начата!"))
    # рассылаем меню «Присоединиться» всем, кто в группе
    async for member in cb.bot.get_chat_members(chat_id):
        try:
            await cb.bot.send_message(
                member.user.id,
                format_info("Нажмите, чтобы присоединиться к игре:"),
                reply_markup=menu_joinable()
            )
        except TelegramBadRequest:
            continue

@router.callback_query(F.data == "ui_join_game")
async def ui_join_game(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    user_id = cb.from_user.id
    user_name = cb.from_user.full_name
    await _join_flow(chat_id, user_id, user_name, cb.bot, feedback=cb.message)
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)

@router.callback_query(F.data == "ui_start_round")
async def ui_start_round(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    st = SESSIONS.get(chat_id)
    host_id = st["players"][st["host_idx"]]["user_id"] if st else None
    await cb.answer()
    if cb.from_user.id != host_id:
        return await cb.message.answer(format_error("Только ведущий может начать раунд"))
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.bot.send_message(host_id, format_info("Раунд начался!"), reply_markup=None)
    await _start_round(cb.bot, chat_id)

async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],
        "hands": {},
        "answers": {},
        "host_idx": -1,
        "current_situation": None,
        "main_deck": [],
        "used_answers": [],
        "scores": {}
    }
    log_event("GAME_CREATE", f"ChatID={chat_id}, Host={host_name}")

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer(format_error("Сначала начните игру"), reply_markup=None)
        return
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(
                user_id,
                format_info("Вы присоединились! Ждём, пока ведущий запустит раунд."),
                reply_markup=None
            )
