from typing import Dict, Any, List
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from game_utils import decks, gen, video_gen  # video_gen для генерации видео

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}

# —————— СТИЛИ ОФОРМЛЕНИЯ ——————

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
        f"┃ {situation[:20]:<18} ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )

def format_answer_card(answer: str, card_num: int) -> str:
    return (
        f"┌────────────────────┐\n"
        f"│ 🃏 КАРТА #{card_num:<2}        │\n"
        f"├────────────────────┤\n"
        f"│ {answer[:18]:<18} │\n"
        f"└────────────────────┘"
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

async def send_animated_message(chat_id: int, text: str, bot: Bot):
    msg = await bot.send_message(chat_id, "…")
    for i in range(1, len(text) + 1):
        await asyncio.sleep(0.05)
        await msg.edit_text(text[:i])

# ——————————————————————————————

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(format_header("Жесткая Игра"), reply_markup=main_menu())

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer(format_header("Игра начата!"), reply_markup=main_menu())

@router.message(Command("join_game"))
async def cmd_join_game(m: Message, bot: Bot):
    await _join_flow(m.chat.id, m.from_user.id, m.from_user.full_name, bot, feedback=m)

@router.message(Command("start_round"))
async def cmd_start_round(m: Message):
    await _start_round(m.bot, m.chat.id)

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name)
    await cb.answer()
    try:
        await cb.message.edit_text(format_header("Игра начата!"), reply_markup=main_menu())
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "ui_join_game")
async def ui_join_game(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback=cb.message)
    await cb.answer()

@router.callback_query(F.data == "ui_start_round")
async def ui_start_round(cb: CallbackQuery):
    await cb.answer()
    await _start_round(cb.bot, cb.message.chat.id)

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

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer(format_header("Сначала нажмите «Начать игру»", style="warning"), reply_markup=main_menu())
        return
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились к игре! Ожидайте начала раунда.")
        except TelegramBadRequest:
            await feedback.answer(format_header(f"{user_name}, нажмите Start у бота и повторите.", style="warning"))
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(f"✅ Игроков: {len(st['players'])}", reply_markup=main_menu())

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, format_header("Нужно минимум 2 игрока", style="warning"), reply_markup=main_menu())
        return

    st["answers"].clear()
    st["hands"].clear()
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    st["current_situation"] = decks.get_random_situation()

    # Анимированная печать карточки ситуации
    round_title = format_header(f"Раунд {st['host_idx']+1}", style="round")
    situation_card = format_situation_card(st["current_situation"], st["host_idx"]+1)
    await send_animated_message(chat_id, f"{round_title}\n\n{situation_card}", bot)

    # Формируем колоду
    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in st["used_answers"]]
    if not st["main_deck"]:
        await bot.send_message(chat_id, format_header("Нет доступных карт", style="warning"))
        return

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host["user_id"]:
            continue
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

    # Отправка карт игрокам с таймером
    for p in st["players"]:
        uid = p["user_id"]
        if uid == host["user_id"]:
            continue
        hand = st["hands"].get(uid, [])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"ans:{chat_id}:{uid}:{i}")]
            for i in range(len(hand))
        ])
        card_title = format_header("Ваша рука", style="main")
        situation_line = f"🎲 Ситуация: {st['current_situation']}"
        message_text = (
            f"{card_title}\n\n"
            f"{situation_line}\n\n"
            f"🎴 У вас {len(hand)} карт."
        )
        try:
            timer_msg = await bot.send_message(uid, message_text, reply_markup=kb)
            for sec in range(30, 0, -1):
                await asyncio.sleep(1)
                try:
                    await timer_msg.edit_text(
                        f"{message_text}\n\n{format_countdown_timer(sec)}",
                        reply_markup=kb
                    )
                except TelegramBadRequest:
                    break
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}.")

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    _, chat_id_str, uid_str, idx_str = cb.data.split(":")
    chat_id, uid, idx = int(chat_id_str), int(uid_str), int(idx_str)
    st = SESSIONS.get(chat_id)
    if not st:
        return await cb.answer(format_header("Игра не найдена", style="warning"), show_alert=True)
    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != uid or uid == host_id:
        return await cb.answer(format_header("Вы не можете отвечать", style="warning"), show_alert=True)
    hand = st["hands"].get(uid, [])
    if idx < 0 or idx >= len(hand):
        return await cb.answer(format_header("Неверный выбор", style="warning"), show_alert=True)

    card = hand.pop(idx)
    st["answers"][uid] = card
    st["used_answers"].append(card)
    await cb.answer(f"✅ Вы выбрали: {card}")

    if len(st["answers"]) >= len(st["players"]) - 1:
        header = format_header("Ответы игроков", style="main")
        lines = []
        buttons = []
        for i, (uid2, ans) in enumerate(st["answers"].items(), 1):
            name = next(p["username"] for p in st["players"] if p["user_id"] == uid2)
            if uid2 == host_id:
                name = f"<b>{name}</b>"
            lines.append(f"{i}. {name} — {ans}")
            buttons.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{chat_id}:{i-1}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await cb.bot.send_message(chat_id, f"{header}\n\n" + "\n".join(lines), parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    _, chat_id_str, idx_str = cb.data.split(":")
    chat_id, idx = int(chat_id_str), int(idx_str)
    st = SESSIONS.get(chat_id)
    if not st:
        return await cb.answer(format_header("Игра не найдена", style="warning"), show_alert=True)
    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != host_id:
        return await cb.answer(format_header("Только ведущий может выбирать", style="warning"), show_alert=True)

    ordered = list(st["answers"].items())
    uid_win, win_ans = ordered[idx]
    win_name = next(p["username"] for p in st["players"] if p["user_id"] == uid_win)

    # Увеличиваем счёт
    st["scores"][win_name] += 1

    result_header = format_header("Результат раунда", style="result")
    result_text = f"{result_header}\n\n🏆 Победитель: {win_name}\nОтвет: {win_ans}"
    try:
        await cb.message.edit_text(result_text, reply_markup=None)
    except TelegramBadRequest:
        pass

    try:
        await video_gen.send_video_illustration(cb.bot, chat_id, st["current_situation"], win_ans)
    except Exception as e:
        await cb.bot.send_message(chat_id, format_header(f"Ошибка видео: {e}", style="warning"))

    # Показ прогресса
    progress = render_scores_ascii(st)
    await cb.bot.send_message(chat_id, progress)

    # Добор карт
    for p in st["players"]:
        uid2 = p["user_id"]
        if uid2 == host_id:
            continue
        if not st["main_deck"]:
            full_deck = decks.get_new_shuffled_answers_deck()
            used = st["used_answers"]
            in_hands = [card for hand in st["hands"].values() for card in hand]
            available_cards = [c for c in full_deck if c not in used and c not in in_hands]
            st["main_deck"] = available_cards
            if not available_cards:
                continue
        new_card = st["main_deck"].pop()
        st["hands"].setdefault(uid2, []).append(new_card)
        try:
            await cb.bot.send_message(
                uid2,
                f"🎴 Вы добрали карту: **{new_card}**\nТеперь у вас {len(st['hands'][uid2])} карт.",
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            pass

    await cb.bot.send_message(chat_id, format_header("Раунд завершён"), reply_markup=main_menu())
