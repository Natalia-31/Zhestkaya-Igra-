from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, video_gen

# ----------- ДОБАВЛЕНО ДЛЯ GEMINI ----------
import google.generativeai as genai
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def generate_gemini_response(situation: str, answer: str) -> str:
    model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
    prompt = f"Ситуация: {situation}\nОтвет игрока: {answer}\nОписание или реакция:"
    response = model.generate_content(prompt)
    return response.text

# ----------- ВАША ОСНОВНАЯ ИГРОВАЯ ЛОГИКА ----------
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
        "players": [],
        "hands": {},
        "answers": {},
        "host_idx": -1,
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

    st["current_situation"] = decks.get_random_situation()
    await bot.send_message(
        chat_id,
        f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {st['current_situation']}"
    )

    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in st["used_answers"]]
    if not st["main_deck"]:
        await bot.send_message(chat_id, "⚠️ Нет доступных карт в колоде.")
        return

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

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
            msg = f"🎲 Ситуация: {st['current_situation']}\n\n🎴 Ваша рука ({len(hand)}). Выберите ответ:"
            await bot.send_message(uid, msg, reply_markup=kb)
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}.")

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    _, group_chat_id_str, uid_str, idx_str = cb.data.split(":")
    group_chat_id, uid, idx = int(group_chat_id_str), int(uid_str), int(idx_str)
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

    need = len(st["players"]) - 1
    if len(st["answers"]) >= need:
        ordered = [(u, st["answers"][u]) for u in st["answers"]]
        lines, buttons = [], []
        for i, (u2, ans) in enumerate(ordered, 1):
            name = next(p["username"] for p in st["players"] if p["user_id"] == u2)
            lines.append(f"{i}. {name} — {ans}")
            buttons.append([InlineKeyboardButton(text=str(i), callback_data=f"pick:{group_chat_id}:{i-1}")])
        await cb.bot.send_message(group_chat_id, "Ответы игроков:\n" + "\n".join(lines),
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    _, group_chat_id_str, idx_str = cb.data.split(":")
    group_chat_id, idx = int(group_chat_id_str), int(idx_str)
    st = SESSIONS.get(group_chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    host_id = st["players"][st["host_idx"]]["user_id"]
    if cb.from_user.id != host_id:
        await cb.answer("Только ведущий может выбирать.", show_alert=True)
        return

    ordered = [(u, st["answers"][u]) for u in st["answers"]]
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

    # -------- ВСТАВЛЕНО: AI-реакция от Gemini --------
    ai_text = await asyncio.to_thread(generate_gemini_response, st["current_situation"], win_ans)
    await cb.bot.send_message(group_chat_id, f"🤖 AI-реакция:\n{ai_text}")

    try:
        await video_gen.send_video_illustration(cb.bot, group_chat_id,
                                                st["current_situation"], win_ans)
    except Exception as e:
        await cb.bot.send_message(group_chat_id, f"⚠️ Не удалось сгенерировать видео: {e}")

    for p in st["players"]:
        uid2 = p["user_id"]
        if uid2 == host_id:
            continue
        if not st["main_deck"]:
            full = decks.get_new_shuffled_answers_deck()
            used = st["used_answers"]
            in_hands = [c for hand in st["hands"].values() for c in hand]
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
