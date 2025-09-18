from typing import Dict, Any
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.iterators import ChatMemberIterator
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
    async for member in ChatMemberIterator(cb.bot, chat_id):
        user = member.user
        if user.is_bot:
            continue
        try:
            await cb.bot.send_message(
                user.id,
                format_info("Нажмите, чтобы присоединиться к игре:"),
                reply_markup=menu_joinable()
            )
        except TelegramBadRequest:
            pass

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
    await cb.bot.send_message(host_id, format_info("Раунд начался!"))
    await _start_round(cb.bot, chat_id)

async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [], "hands": {}, "answers": {},
        "host_idx": -1, "current_situation": None,
        "main_deck": [], "used_answers": [], "scores": {}
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
                format_info("Вы присоединились! Ждём запуска раунда."),
                reply_markup=None
            )
        except TelegramBadRequest:
            await feedback.answer(format_error("Невозможно отправить ЛС"), reply_markup=None)
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(format_info(f"Игроков: {len(st['players'])}"))

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        return await bot.send_message(chat_id, format_error("Нужно минимум 2 игрока"))
    st["answers"].clear()
    st["hands"].clear()
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    st["current_situation"] = decks.get_random_situation()
    log_event("ROUND_START", f"ChatID={chat_id}, Round={st['host_idx']+1}")

    title = format_header(f"Раунд {st['host_idx']+1}", "round")
    card = format_situation_card(st["current_situation"], st["host_idx"]+1)
    await send_gray_card(chat_id, f"{title}\n\n{card}", bot)

    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in st["used_answers"]]

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host["user_id"]:
            continue
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host["user_id"]:
            continue
        hand = st["hands"][uid]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"ans:{chat_id}:{uid}:{i}")]
            for i in range(len(hand))
        ])
        text = f"{format_header('Ваша рука','main')}\n\n🎲 {st['current_situation']}\n\n🎴 У вас {len(hand)} карт."
        try:
            msg = await bot.send_message(uid, text, reply_markup=kb)
            for sec in range(30, 0, -1):
                await asyncio.sleep(1)
                try:
                    await msg.edit_text(f"{text}\n\n{format_countdown_timer(sec)}", reply_markup=kb)
                except TelegramBadRequest:
                    break
        except TelegramBadRequest:
            await bot.send_message(chat_id, format_error(f"Не могу отправить {p['username']}"))

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    _, chat_id_str, uid_str, idx_str = cb.data.split(":")
    chat_id, uid, idx = map(int, (chat_id_str, uid_str, idx_str))
    st = SESSIONS.get(chat_id)
    if not st:
        return await cb.answer(format_error("Игра не найдена"), show_alert=True)
    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != uid or uid == host_id:
        return await cb.answer(format_error("Вы не можете отвечать"), show_alert=True)
    hand = st["hands"][uid]
    if idx < 0 or idx >= len(hand):
        return await cb.answer(format_error("Неверный выбор"), show_alert=True)

    card = hand.pop(idx)
    st["answers"][uid] = card
    st["used_answers"].append(card)
    await cb.answer(format_info(f"Вы выбрали: {card}"))

    if len(st["answers"]) >= len(st["players"]) - 1:
        header = format_header("Ответы игроков","main")
        lines, buttons = [], []
        for i,(uid2,ans) in enumerate(st["answers"].items(),1):
            name = next(p["username"] for p in st["players"] if p["user_id"]==uid2)
            if uid2==host_id: name=f"<b>{name}</b>"
            lines.append(f"{i}. {name} — {ans}")
            buttons.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{chat_id}:{i-1}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await send_gray_card(chat_id, f"{header}\n\n"+"\n".join(lines), cb.bot)
        await cb.bot.send_message(chat_id, format_info("Выберите победителя:"), reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    _, chat_id_str, idx_str = cb.data.split(":")
    chat_id, idx = map(int, (chat_id_str, idx_str))
    st = SESSIONS.get(chat_id)
    if not st:
        return await cb.answer(format_error("Игра не найдена"), show_alert=True)
    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != host_id:
        return await cb.answer(format_error("Только ведущий может выбирать"), show_alert=True)

    uid_win, win_ans = list(st["answers"].items())[idx]
    win_name = next(p["username"] for p in st["players"] if p["user_id"]==uid_win)
    st["scores"][win_name] += 1
    log_event("WINNER_PICK", f"ChatID={chat_id}, Winner={win_name}")

    result_header = format_header("Результат раунда","result")
    result_text = f"{result_header}\n\n🏆 Победитель: {win_name}\nОтвет: {win_ans}"
    await send_gray_card(chat_id, result_text, cb.bot)
    await cb.bot.send_message(chat_id, render_scores_ascii(st))
    await cb.bot.send_message(host_id, format_info("Готово к новому раунду"), reply_markup=menu_for_host())
