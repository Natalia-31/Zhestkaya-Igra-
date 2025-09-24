# handlers/game_handlers.py

from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from config import OPENAI_SETTINGS
from game_utils import generate_image_bytes
from image_generator import create_card
from decks import get_new_shuffled_answers_deck

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню.", reply_markup=main_menu())

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer("✅ Игра начата!", reply_markup=main_menu())

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
        await cb.message.edit_text("✅ Игра начата!", reply_markup=main_menu())
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
        "players": [{"user_id": host_id, "username": host_name}],
        "hands": {},
        "answers": {},
        "host_idx": 0,
        "current_situation": None,
        "main_deck": [],
        "used_answers": []
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
            await feedback.answer(f"⚠️ {user_name}, нажмите Start у бота и повторите. {e}")
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(f"✅ Игроков: {len(st['players'])}", reply_markup=main_menu())

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Нужно минимум 2 игрока.", reply_markup=main_menu())
        return

    st["answers"].clear()
    st["hands"].clear()
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    host_id = host["user_id"]

    # Предварительно сгенерированная ситуация
    situation = "Придумайте забавную ситуацию для карточной игры."
    st["current_situation"] = situation

    await bot.send_message(
        chat_id,
        f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {situation}"
    )

    full_deck = get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in st["used_answers"]]
    if not st["main_deck"]:
        await bot.send_message(chat_id, "⚠️ Нет доступных карт в колоде.")
        return

    # Раздача карт
    hand_size = OPENAI_SETTINGS.get("HAND_SIZE", 10)
    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        st["hands"][uid] = [st["main_deck"].pop() for _ in range(min(hand_size, len(st["main_deck"])))]

    # Отправка карт игрокам
    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        hand = st["hands"].get(uid, [])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{uid}:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(
                uid,
                f"🎲 Ситуация: {situation}\n\n🎴 Ваша рука ({len(hand)}). Выберите ответ:",
                reply_markup=kb
            )
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}.")

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    _, gcid, uid, idx = cb.data.split(":")
    group_chat_id, uid, idx = int(gcid), int(uid), int(idx)
    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != uid or uid == host_id:
        await cb.answer("Вы не можете отвечать.", show_alert=True)
        return

    hand = st["hands"].get(uid, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    card = hand.pop(idx)
    st["answers"][uid] = card
    st["used_answers"].append(card)
    await cb.answer(f"Вы выбрали: {card}")

    if len(st["answers"]) >= len(st["players"]) - 1:
        ordered = list(st["answers"].items())
        lines, buttons = [], []
        for i, (u2, ans) in enumerate(ordered, 1):
            name = next(p["username"] for p in st["players"] if p["user_id"] == u2)
            lines.append(f"{i}. {name} — {ans}")
            buttons.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{group_chat_id}:{i-1}")])
        await cb.bot.send_message(
            group_chat_id,
            "Ответы игроков:\n" + "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    _, gcid, idx = cb.data.split(":")
    group_chat_id, idx = int(gcid), int(idx)
    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != host_id:
        await cb.answer("Только ведущий может выбирать.", show_alert=True)
        return

    ordered = list(st["answers"].items())
    if idx < 0 or idx >= len(ordered):
        await cb.answer("Неверный индекс.", show_alert=True)
        return

    win_uid, win_ans = ordered[idx]
    win_name = next(p["username"] for p in st["players"] if p["user_id"] == win_uid)

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await cb.message.edit_text(f"🏆 Победитель: {win_name}\nОтвет: {win_ans}")

    # Генерация и отправка иллюстрации
    try:
        img_bytes = generate_image_bytes(f"{st['current_situation']} Ответ: {win_ans}")
        if img_bytes:
            await cb.bot.send_photo(group_chat_id, img_bytes)
    except Exception as e:
        await cb.bot.send_message(group_chat_id, f"⚠️ Ошибка иллюстрации: {e}")

    # Добор карт
    for p in st["players"]:
        uid2 = p["user_id"]
        if uid2 == host_id:
            continue
        if not st["main_deck"]:
            full = get_new_shuffled_answers_deck()
            used = set(st["used_answers"])
            in_hands = {c for hand in st["hands"].values() for c in hand}
            st["main_deck"] = [c for c in full if c not in used and c not in in_hands]
        if st["main_deck"]:
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

    await cb.bot.send_message(group_chat_id, "Раунд завершён.", reply_markup=main_menu())
