from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
import json
import random
from game_utils import gen, get_random_situation

router = Router()
HAND_SIZE = 10
GAMES = {}  # chat_id → { players, host_index, situation, hands, answers }

# Загрузка колоды карт
with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="▶️ Начать игру", callback_data="new_game"),
            InlineKeyboardButton(text="➕ Присоединиться", callback_data="join_game"),
            InlineKeyboardButton(text="🎲 Новый раунд", callback_data="start_round"),
        ]]
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = {
        "players": [],
        "host_index": 0,
        "situation": None,
        "hands": {},
        "answers": []
    }
    await message.answer(
        "✅ Игра начата! Игроки могут присоединиться командой /join_game или кнопкой ниже.",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "new_game")
async def cb_new_game(callback: CallbackQuery):
    GAMES[callback.message.chat.id] = {
        "players": [],
        "host_index": 0,
        "situation": None,
        "hands": {},
        "answers": []
    }
    await callback.answer("Игра начата!", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=main_menu_kb())

@router.message(Command("join_game"))
async def cmd_join_game(message: Message):
    game = GAMES.get(message.chat.id)
    if not game:
        return await message.answer("Сначала начните игру: /new_game", reply_markup=main_menu_kb())
    uid = message.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await message.answer(
        f"➕ {message.from_user.full_name} присоединился!",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery):
    game = GAMES.get(callback.message.chat.id)
    if not game:
        return await callback.answer("Сначала начните игру.", show_alert=True)
    uid = callback.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await callback.answer(f"{callback.from_user.full_name} присоединился!", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=main_menu_kb())

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    await _start_round_logic(message.bot, message.chat.id, message.from_user.id)

@router.callback_query(F.data == "start_round")
async def cb_start_round(callback: CallbackQuery):
    await callback.answer()
    await _start_round_logic(callback.bot, callback.message.chat.id, callback.from_user.id)

async def _start_round_logic(bot: Bot, chat_id: int, starter_id: int):
    game = GAMES.get(chat_id)
    if not game or not game["players"]:
        return await bot.send_message(chat_id, "Сначала /new_game и /join_game", reply_markup=main_menu_kb())
    # Определяем ведущего по кругу
    idx = game["host_index"] % len(game["players"])
    host_id = game["players"][idx]
    game["host_index"] += 1
    game["answers"].clear()
    game["hands"].clear()
    # Ситуация
    situation = get_random_situation()
    game["situation"] = situation
    host_member = await bot.get_chat_member(chat_id, host_id)
    host_name = host_member.user.full_name
    await bot.send_message(
        chat_id,
        f"🎬 Раунд начался! 👑 Ведущий: {host_name}\n\n🎲 {situation}"
    )
    # Генерируем и отправляем иллюстрацию ситуации
    await gen.send_situation_with_image(bot, chat_id)
    # Раздаём карты
    deck = ALL_CARDS.copy()
    random.shuffle(deck)
    for uid in game["players"]:
        if uid == host_id:
            continue
        hand = [deck.pop() for _ in range(HAND_SIZE)]
        game["hands"][uid] = hand
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=card, callback_data=f"ans:{i}")]
                for i, card in enumerate(hand)
            ]
        )
        try:
            await bot.send_message(uid, "Ваша рука — выберите карту-ответ:", reply_markup=kb)
        except:
            pass  # Если бот не может написать в личку

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    uid = callback.from_user.id
    game = GAMES.get(chat_id)
    if not game:
        return
    # Ведущий не отвечает
    host_idx = (game["host_index"] - 1) % len(game["players"])
    if uid == game["players"][host_idx]:
        return await callback.answer("Ведущий не отвечает.", show_alert=True)
    idx = int(callback.data.split(":", 1)[1])
    hand = game["hands"].get(uid, [])
    if idx < 0 or idx >= len(hand):
        return await callback.answer("Неверный выбор.", show_alert=True)
    card = hand.pop(idx)
    game["answers"].append((uid, card))
    await callback.answer(f"Вы выбрали: {card}")
    # Если все ответили
    if len(game["answers"]) >= len(game["players"]) - 1:
        text = "Ответы игроков:\n" + "\n".join(f"{i+1}. {c}" for i, (_, c) in enumerate(game["answers"]))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=str(i+1), callback_data=f"pick:{i}")]
                for i in range(len(game["answers"]))
            ]
        )
        await bot.send_message(chat_id, text, reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = GAMES.get(chat_id)
    if not game:
        return
    # Только ведущий выбирает
    host_idx = (game["host_index"] - 1) % len(game["players"])
    host_id = game["players"][host_idx]
    if callback.from_user.id != host_id:
        return await callback.answer("Только ведущий может выбирать.", show_alert=True)
    idx = int(callback.data.split(":", 1)[1])
    uid, card = game["answers"][idx]
    winner_member = await callback.bot.get_chat_member(chat_id, uid)
    winner_name = winner_member.user.full_name
    await callback.message.edit_text(f"🏆 Победитель: {winner_name}\nОтвет: {card}")
    # Генерация финальной иллюстрации
    combined = f"{game['situation']} ____ {card}"
    image_path = await gen.generate_image_from_situation(combined, f"round_{chat_id}")
    if image_path:
        await callback.bot.send_photo(chat_id, photo=image_path)
    # Меню для нового раунда
    await callback.bot.send_message(chat_id, "Используйте меню для нового раунда:", reply_markup=main_menu_kb())
