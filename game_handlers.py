# handlers/game_handlers.py — ответы из answers.json, ЛС с кнопками, выбор победителя

from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, gen  # колоды (answers/situations) и генерация

router = Router()

# Простая сессия по чату
SESSIONS: Dict[int, Dict[str, Any]] = {}  # chat_id -> state

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню ниже.", reply_markup=main_menu())  # [21]

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer("✅ Игра начата! Нажмите “Присоединиться”, затем “Новый раунд”.", reply_markup=main_menu())  # [21]

@router.message(Command("join_game"))
async def cmd_join_game(m: Message, bot: Bot):
    await _join_flow(m.chat.id, m.from_user.id, m.from_user.full_name, bot, feedback=m)  # [6]

@router.message(Command("start_round"))
async def cmd_start_round(m: Message):
    await _start_round(m.bot, m.chat.id)  # [21]

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name)
    await cb.answer()  # [22]
    try:
        await cb.message.edit_text("✅ Игра начата! Нажмите “Присоединиться”, затем “Новый раунд”.", reply_markup=main_menu())  # [21]
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "ui_join_game")
async def ui_join_game(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback=cb.message)  # [6]
    await cb.answer()  # [22]

@router.callback_query(F.data == "ui_start_round")
async def ui_start_round(cb: CallbackQuery):
    await cb.answer()  # [22]
    await _start_round(cb.bot, cb.message.chat.id)  # [21]

async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],          # [{user_id, username}]
        "hands": {},            # user_id -> List[str]
        "answers": {},          # user_id -> str
        "host_idx": -1,
        "current_situation": None,
        "main_deck": [],        # ответы из answers.json
    }

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer("Сначала “Начать игру”.", reply_markup=main_menu())  # [21]
        return
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились! Ожидайте начала раунда.")  # [6]
        except TelegramBadRequest as e:
            await feedback.answer(f"⚠️ {user_name}, нажмите Start у бота в ЛС и повторите. {e}")  # [23]
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(f"✅ Игроков: {len(st['players'])}", reply_markup=main_menu())  # [21]

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Нужно минимум 2 игрока: нажмите “Присоединиться”.", reply_markup=main_menu())  # [21]
        return

    # Сброс раунда
    st["answers"].clear()
    st["hands"].clear()

    # Ведущий по кругу
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]

    # Ситуация из situations.json через DeckManager
    st["current_situation"] = decks.get_random_situation()  # [14]
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {st['current_situation']}")  # [21]

    # Основная колода из answers.json + раздача по 10 карт
    st["main_deck"] = decks.get_new_shuffled_answers_deck()  # [14]
    if not st["main_deck"]:
        await bot.send_message(chat_id, "⚠️ answers.json пуст — раздавать нечего.")  # [21]
        return

    for p in st["players"]:
        uid = p["user_id"]
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

    # Отправляем руки в ЛС инлайн‑кнопками ans:<uid>:<index>
    for p in st["players"]:
        uid = p["user_id"]
        hand = st["hands"].get(uid, [])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{uid}:{i}")]
            for i, card in enumerate(hand)
        ])  # [2][3]
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({len(hand)} карт). Выберите ответ:", reply_markup=kb)  # [6]
        except TelegramBadRequest as e:
            await bot.send_message(chat_id, f"⚠️ Не могу написать {p['username']} ({uid}) в ЛС. Нажмите Start у бота. {e}")  # [23]

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    # Формат: ans:<uid>:<idx>
    try:
        _, uid_str, idx_str = cb.data.split(":")
        uid_from_btn = int(uid_str)
        idx = int(idx_str)
    except Exception:
        await cb.answer("Некорректные данные.", show_alert=True)  # [22]
        return

    chat_id = cb.message.chat.id
    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)  # [22]
        return

    # Жать может только владелец руки
    if cb.from_user.id != uid_from_btn:
        await cb.answer("Это не ваша рука.", show_alert=True)  # [22]
        return

    hand = st["hands"].get(uid_from_btn, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неверный выбор.", show_alert=True)  # [22]
        return

    card = hand.pop(idx)
    st["answers"][uid_from_btn] = card
    await cb.answer(f"Вы выбрали: {card}")  # [24]

    # Если все, кроме ведущего, ответили — публикуем список
    players_ids = [p["user_id"] for p in st["players"]]
    host_id = players_ids[st["host_idx"]]
    need_count = len(players_ids) - 1
    if len(st["answers"]) >= need_count:
        ordered = [(uid, st["answers"][uid]) for uid in st["answers"]]
        lines = []
        rows = []
        for i, (uid, ans) in enumerate(ordered, start=1):
            uname = next(p["username"] for p in st["players"] if p["user_id"] == uid)
            lines.append(f"{i}. {uname} — {ans}")
            rows.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{i-1}")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)  # [2]
        await cb.message.answer("Ответы игроков:\n" + "\n".join(lines), reply_markup=kb)  # [21]

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)  # [22]
        return

    players_ids = [p["user_id"] for p in st["players"]]
    host_id = players_ids[st["host_idx"]]
    if cb.from_user.id != host_id:
        await cb.answer("Только ведущий может выбрать.", show_alert=True)  # [22]
        return

    try:
        idx = int(cb.data.split(":", 1)[25])
    except Exception:
        await cb.answer("Некорректные данные.", show_alert=True)  # [22]
        return

    ordered = [(uid, st["answers"][uid]) for uid in st["answers"]]
    if idx < 0 or idx >= len(ordered):
        await cb.answer("Неверный индекс.", show_alert=True)  # [22]
        return

    win_uid, win_answer = ordered[idx]
    win_name = next(p["username"] for p in st["players"] if p["user_id"] == win_uid)

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await cb.message.edit_text(f"🏆 Победитель: {win_name}\nОтвет: {win_answer}")  # [21]

    # Генерация изображения по ситуации и победившему ответу
    await gen.send_illustration(cb.bot, chat_id, st["current_situation"], win_answer)  # [6]

    # Добор по 1 карте каждому
    for p in st["players"]:
        uid = p["user_id"]
        # если колода исчерпана — перетасовать заново
        if not st["main_deck"]:
            st["main_deck"] = decks.get_new_shuffled_answers_deck()  # [14]
            if not st["main_deck"]:
                continue
        new_card = st["main_deck"].pop()
        st["hands"].setdefault(uid, []).append(new_card)
        try:
            await cb.bot.send_message(uid, f"Вы добрали карту: `{new_card}`", parse_mode="Markdown")  # [6]
        except TelegramBadRequest:
            pass

    await cb.bot.send_message(chat_id, "Раунд завершён. Нажмите “🎲 Новый раунд”, чтобы продолжить.", reply_markup=main_menu())  # [21]
