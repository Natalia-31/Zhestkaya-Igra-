# handlers/game_handlers.py

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import json
from game_utils import gen, get_random_situation
from game_logic import GameSession

router = Router()
with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)

# Хранилище сессий, ключ - ID группового чата
SESSIONS = {}

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Начать игру", callback_data="new_game"),
        InlineKeyboardButton(text="➕ Присоединиться", callback_data="join_game"),
        InlineKeyboardButton(text="🎲 Новый раунд", callback_data="start_round"),
    ]])

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🎮 Жесткая Игра\n\n"
        "/new_game — начать игру\n"
        "/join_game — присоединиться к игре\n"
        "/start_round — запустить новый раунд",
        reply_markup=main_menu_kb()
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    session = GameSession(message.chat.id)
    SESSIONS[message.chat.id] = session
    await message.answer("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())

@router.callback_query(F.data == "new_game")
async def cb_new_game(callback: CallbackQuery):
    session = GameSession(callback.message.chat.id)
    SESSIONS[callback.message.chat.id] = session
    await callback.answer("Игра начата!")
    try:
        await callback.message.edit_text("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())
    except TelegramBadRequest:
        pass

@router.message(Command("join_game"))
async def cmd_join_game(message: Message):
    session = SESSIONS.get(message.chat.id)
    if not session:
        return await message.answer("Сначала /new_game", reply_markup=main_menu_kb())
    session.add_player(message.from_user.id, message.from_user.full_name)
    count = len(session.players)
    await message.answer(f"➕ {message.from_user.full_name} присоединился! Сейчас игроков: {count}", reply_markup=main_menu_kb())

@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery):
    session = SESSIONS.get(callback.message.chat.id)
    if not session:
        return await callback.answer("Сначала /new_game", show_alert=True)
    session.add_player(callback.from_user.id, callback.from_user.full_name)
    count = len(session.players)
    await callback.answer(f"{callback.from_user.full_name} присоединился! Всего игроков: {count}")
    try:
        await callback.message.edit_text(f"✅ Игра начата! Пока игроков: {count}", reply_markup=main_menu_kb())
    except TelegramBadRequest:
        pass

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    await _start_round_logic(message.bot, message.chat.id)

@router.callback_query(F.data == "start_round")
async def cb_start_round(callback: CallbackQuery):
    await callback.answer()
    await _start_round_logic(callback.bot, callback.message.chat.id)

async def _start_round_logic(bot: Bot, chat_id: int):
    session = SESSIONS.get(chat_id)
    if not session or len(session.players) < 2:
        return await bot.send_message(chat_id, "Нужно минимум 2 игрока: /join_game", reply_markup=main_menu_kb())

    mentions = [f"• {p['username']}" for p in session.players]
    await bot.send_message(chat_id, f"👥 Присоединились ({len(mentions)}):\n" + "\n".join(mentions))

    host = session.next_host()
    session.reset_round()
    situation = session.current_situation = get_random_situation()
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {situation}")

    session.deal_hands(ALL_CARDS)
    for uid, hand in session.hands.items():
        # ВАЖНО: передаем ID группового чата в callback_data
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({len(hand)} карт) — выберите карту-ответ:", reply_markup=kb)
        except Exception:
            pass

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(callback: CallbackQuery, bot: Bot):
    # Извлекаем ID группы и индекс карты из callback_data
    _, group_chat_id_str, idx_str = callback.data.split(":")
    group_chat_id = int(group_chat_id_str)
    idx = int(idx_str)

    # Находим сессию по ID группы, а не личного чата
    session = SESSIONS.get(group_chat_id)
    if not session:
        await callback.answer("Эта игровая сессия устарела или не найдена.", show_alert=True)
        return

    uid = callback.from_user.id
    host = session.get_host()
    if not host or uid == host['user_id']:
        return await callback.answer("Ведущий не отвечает.", show_alert=True)

    hand = session.hands.get(uid, [])
    if idx >= len(hand):
        return await callback.answer("Неверный выбор.", show_alert=True)

    card = hand[idx]
    session.answers[uid] = card
    await callback.answer(f"Вы выбрали: {card}")
    try:
        await callback.message.edit_text(f"Вы выбрали карту:\n\n✅ *{card}*\n\nОжидаем других игроков...", parse_mode="Markdown")
    except TelegramBadRequest: # Если сообщение не изменилось, ничего страшного
        pass

    if session.all_answers_received():
        answers_list = list(session.answers.values())
        text = "Ответы игроков:\n" + "\n".join(f"{i+1}. {ans}" for i, ans in enumerate(answers_list))
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"pick:{group_chat_id}:{i}")]
            for i in range(len(answers_list))
        ])
        # Отправляем сообщение в групповой чат
        await bot.send_message(group_chat_id, text, reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(callback: CallbackQuery, bot: Bot):
    # Извлекаем ID группы и индекс карты из callback_data
    _, group_chat_id_str, idx_str = callback.data.split(":")
    group_chat_id = int(group_chat_id_str)
    idx = int(idx_str)

    session = SESSIONS.get(group_chat_id)
    if not session:
        await callback.answer("Сессия устарела.", show_alert=True)
        return

    host = session.get_host()
    if not host or callback.from_user.id != host['user_id']:
        return await callback.answer("Только ведущий может выбирать.", show_alert=True)

    winner_info = session.pick_winner(idx)
    if winner_info:
        await callback.message.edit_text(f"🏆 Победитель: {winner_info['username']}\nОтвет: {winner_info['answer']}")
        await gen.generate_and_send_image(bot, group_chat_id, session.current_situation, winner_info["answer"])
    
    await bot.send_message(group_chat_id, "Используйте меню для нового раунда:", reply_markup=main_menu_kb())
