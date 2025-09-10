from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json, random
from game_utils import gen, get_random_situation

router = Router()
HAND_SIZE = 10
GAMES = {}  # chat_id → { players, host_index, situation, hands, answers }

with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton("▶️ Начать игру", callback_data="new_game"),
        InlineKeyboardButton("➕ Присоединиться", callback_data="join_game"),
        InlineKeyboardButton("🎲 Новый раунд", callback_data="start_round"),
    ]])

@router.message(Command("new_game"))
async def cmd_new_game(msg: Message):
    GAMES[msg.chat.id] = {"players": [], "host_index": 0, "situation": None, "hands": {}, "answers": []}
    await msg.answer("✅ Игра начата! Присоединяйтесь:", reply_markup=main_menu_kb())

@router.callback_query(F.data=="new_game")
async def cb_new_game(cb: CallbackQuery):
    GAMES[cb.message.chat.id] = {"players": [], "host_index": 0, "situation": None, "hands": {}, "answers": []}
    await cb.answer("Игра начата!")

@router.message(Command("join_game"))
async def cmd_join_game(msg: Message):
    game = GAMES.get(msg.chat.id)
    if not game:
        return await msg.answer("Сначала /new_game")
    uid = msg.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await msg.answer(f"➕ {msg.from_user.full_name} присоединился!", reply_markup=main_menu_kb())

@router.callback_query(F.data=="join_game")
async def cb_join_game(cb: CallbackQuery):
    game = GAMES.get(cb.message.chat.id)
    if not game:
        return await cb.answer("Сначала /new_game", show_alert=True)
    uid = cb.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await cb.answer(f"{cb.from_user.full_name} присоединился!")

@router.message(Command("start_round"))
async def cmd_start_round(msg: Message):
    await _start_round(msg.bot, msg.chat.id, msg.from_user.id)

@router.callback_query(F.data=="start_round")
async def cb_start_round(cb: CallbackQuery):
    await cb.answer()
    await _start_round(cb.bot, cb.message.chat.id, cb.from_user.id)

async def _start_round(bot: Bot, chat_id: int, starter_id: int):
    game = GAMES.get(chat_id)
    if not game or not game["players"]:
        return await bot.send_message(chat_id, "Сначала /new_game и /join_game")
    idx = game["host_index"] % len(game["players"])
    host_id = game["players"][idx]
    game["host_index"] += 1
    game["answers"].clear()
    game["hands"].clear()

    sit = get_random_situation()
    game["situation"] = sit
    host_name = (await bot.get_chat_member(chat_id, host_id)).user.full_name
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host_name}\n\n🎲 {sit}")
    # generate and send situation illustration
    await gen.send_situation_with_image(bot, chat_id)

    deck = ALL_CARDS.copy(); random.shuffle(deck)
    for uid in game["players"]:
        if uid==host_id: continue
        hand=[deck.pop() for _ in range(HAND_SIZE)]
        game["hands"][uid]=hand
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(card, callback_data=f"ans:{i}")]
            for i,card in enumerate(hand)
        ])
        try: await bot.send_message(uid,"Ваша рука — выберите карту:",reply_markup=kb)
        except: pass

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(cb: CallbackQuery):
    chat_id=cb.message.chat.id; uid=cb.from_user.id; game=GAMES.get(chat_id)
    # host cannot answer
    host_idx=(game["host_index"]-1)%len(game["players"])
    if uid==game["players"][host_idx]:
        return await cb.answer("Ведущий не отвечает.",True)
    idx=int(cb.data.split(":",1)[1])
    hand=game["hands"].get(uid,[])
    if idx<0 or idx>=len(hand): return await cb.answer("Неверно.",True)
    card=hand.pop(idx)
    game["answers"].append((uid,card))
    await cb.answer(f"Вы выбрали: {card}")
    if len(game["answers"])>=len(game["players"])-1:
        text="Ответы:\n"+ "\n".join(f"{i+1}. {c}" for i,(_,c) in enumerate(game["answers"]))
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(str(i+1),callback_data=f"pick:{i}")]
            for i in range(len(game["answers"]))
        ])
        await cb.bot.send_message(chat_id,text,reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(cb: CallbackQuery):
    chat_id=cb.message.chat.id; game=GAMES.get(chat_id)
    host_idx=(game["host_index"]-1)%len(game["players"]); host_id=game["players"][host_idx]
    if cb.from_user.id!=host_id:
        return await cb.answer("Только ведущий.",True)
    idx=int(cb.data.split(":",1)[1])
    uid,card=game["answers"][idx]
    winner_name=(await cb.bot.get_chat_member(chat_id,uid)).user.full_name
    await cb.message.edit_text(f"🏆 Победитель: {winner_name}\nОтвет: {card}")
    combined=f"{game['situation']} ____ {card}"
    img_path=await gen.generate_image_from_situation(combined,f"round_{chat_id}")
    if img_path:
        await cb.bot.send_photo(chat_id,photo=img_path)
    await cb.bot.send_message(chat_id,"Нажмите кнопку «Новый раунд» или /start_round",reply_markup=main_menu_kb())
