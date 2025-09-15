# handlers/game_handlers.py — исправлены callback с group_chat_id и синтаксические ошибки

from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, gen

router = Router()

# Простая сессия по чату
SESSIONS: Dict[int, Dict[str, Any]] = {}

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню ниже.", reply_markup=main_menu())

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer("✅ Игра начата! Нажмите «Присоединиться», затем «Новый раунд».", reply_markup=main_menu())

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
        await cb.message.edit_text("✅ Игра начата! Нажмите «Присоединиться», затем «Новый раунд».", reply_markup=main_menu())
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
        await feedback.answer("Сначала нажмите «Начать игру».", reply_markup=main_menu())
        return
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились к игре! Ожидайте начала раунда.")
        except TelegramBadRequest as e:
            await feedback.answer(f"⚠️ {user_name}, нажмите Start у бота в ЛС и повторите. {e}")
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(f"✅ Игроков: {len(st['players'])}", reply_markup=main_menu())

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Нужно минимум 2 игрока: нажмите «Присоединиться».", reply_markup=main_menu())
        return

    # Сброс раунда
    st["answers"].clear()
    st["hands"].clear()

    # Ведущий по кругу
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]

    # Ситуация из situations.json через DeckManager
    st["current_situation"] = decks.get_random_situation()
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {st['current_situation']}")

    # Основная колода из answers.json + раздача по 10 карт
    st["main_deck"] = decks.get_new_shuffled_answers_deck()
    if not st["main_deck"]:
        await bot.send_message(chat_id, "⚠️ answers.json пуст — раздавать нечего.")
        return

    for p in st["players"]:
        uid = p["user_id"]
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

    # Отправляем руки в ЛС инлайн-кнопками с group_chat_id
    for p in st["players"]:
        uid = p["user_id"]
        hand = st["hands"].get(uid, [])
        # ИСПРАВЛЕНИЕ: передаем group_chat_id в callback_data
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{uid}:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({len(hand)} карт). Выберите ответ:", reply_markup=kb)
        except TelegramBadRequest as e:
            await bot.send_message(chat_id, f"⚠️ Не могу написать {p['username']} ({uid}) в ЛС. Нажмите Start у бота. {e}")

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    # ИСПРАВЛЕНИЕ: формат ans:<group_chat_id>:<uid>:<idx>
    try:
        _, group_chat_id_str, uid_str, idx_str = cb.data.split(":")
        group_chat_id = int(group_chat_id_str)
        uid_from_btn = int(uid_str)
        idx = int(idx_str)
    except Exception:
        await cb.answer("Некорректные данные.", show_alert=True)
        return

    # ИСПРАВЛЕНИЕ: ищем сессию по group_chat_id
    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    # Жать может только владелец руки
    if cb.from_user.id != uid_from_btn:
        await cb.answer("Это не ваша рука.", show_alert=True)
        return

    hand = st["hands"].get(uid_from_btn, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    card = hand.pop(idx)
    st["answers"][uid_from_btn] = card
    await cb.answer(f"Вы выбрали: {card}")

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
            # ИСПРАВЛЕНИЕ: передаем group_chat_id в callback для выбора победителя
            rows.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{group_chat_id}:{i-1}")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await cb.bot.send_message(group_chat_id, "Ответы игроков:\n" + "\n".join(lines), reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    # ИСПРАВЛЕНИЕ: формат pick:<group_chat_id>:<idx>
    try:
        _, group_chat_id_str, idx_str = cb.data.split(":")
        group_chat_id = int(group_chat_id_str)
        idx = int(idx_str)
    except Exception:
        await cb.answer("Некорректные данные.", show_alert=True)
        return

    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    players_ids = [p["user_id"] for p in st["players"]]
    host_id = players_ids[st["host_idx"]]
    if cb.from_user.id != host_id:
        await cb.answer("Только ведущий может выбрать.", show_alert=True)
        return

    ordered = [(uid, st["answers"][uid]) for uid in st["answers"]]
    if idx < 0 or idx >= len(ordered):
        await cb.answer("Неверный индекс.", show_alert=True)
        return

    win_uid, win_answer = ordered[idx]
    win_name = next(p["username"] for p in st["players"] if p["user_id"] == win_uid)

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await cb.message.edit_text(f"🏆 Победитель: {win_name}\nОтвет: {win_answer}")

    # Генерация изображения по ситуации и победившему ответу
    await gen.send_illustration(cb.bot, group_chat_id, st["current_situation"], win_answer)

    # Добор по 1 карте каждому
    for p in st["players"]:
        uid = p["user_id"]
        # если колода исчерпана — перетасовать заново
        if not st["main_deck"]:
            st["main_deck"] = decks.get_new_shuffled_answers_deck()
            if not st["main_deck"]:
                continue
        new_card = st["main_deck"].pop()
        st["hands"].setdefault(uid, []).append(new_card)
        try:
            await cb.bot.send_message(uid, f"Вы добрали карту: `{new_card}`", parse_mode="Markdown")
        except TelegramBadRequest:
            pass

    # ИСПРАВЛЕНИЕ: убраны проблемные кавычки с emoji
    await cb.bot.send_message(group_chat_id, "Раунд завершён. Нажмите «Новый раунд», чтобы продолжить.", reply_markup=main_menu())
