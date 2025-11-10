# handlers/game_handlers.py
import asyncio
import os
import random
from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, generate_card_content
from card_generator import create_situation_card

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}

# Глобальные переменные для ботов (будут установлены при инициализации)
BOT_PLAYERS: List = []

def set_bot_players(bot_players: list):
    """Устанавливает список ботов-игроков"""
    global BOT_PLAYERS
    BOT_PLAYERS = bot_players
    print(f"✅ Зарегистрировано ботов: {len(BOT_PLAYERS)}")

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="Новый раунд", callback_data="ui_start_round")],
        [InlineKeyboardButton(text="Статистика", callback_data="ui_stats")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    # Приветственное видео
    WELCOME_VIDEO_PATH = "assets/welcome.mp4"
    try:
        if os.path.exists(WELCOME_VIDEO_PATH):
            video = FSInputFile(WELCOME_VIDEO_PATH)
            await m.bot.send_video(
                chat_id=m.chat.id,
                video=video,
                caption="🎮 Добро пожаловать в Жесткую Игру!\n\n"
                        "В игре участвуют 2 бота-игрока: 🤖 БотИгрок1 и 🤖 БотИгрок2"
            )
    except Exception as e:
        print(f"⚠️ Ошибка отправки видео: {e}")
    
    # Меню с кнопками
    await m.answer("Используйте меню для управления игрой:", reply_markup=main_menu())

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name, m.bot)
    await m.answer("Игра начата! В игре участвуют два бота-игрока.", reply_markup=main_menu())

@router.message(Command("join_game"))
async def cmd_join_game(m: Message, bot: Bot):
    await _join_flow(m.chat.id, m.from_user.id, m.from_user.full_name, bot, feedback=m)

@router.message(Command("start_round"))
async def cmd_start_round(m: Message):
    await _start_round(m.bot, m.chat.id)

@router.message(Command("stats"))
async def cmd_stats(m: Message):
    await _show_stats(m.chat.id, m)

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, cb.bot)
    await cb.answer()
    try:
        await cb.message.edit_text("Игра начата! В игре участвуют два бота-игрока.", reply_markup=main_menu())
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

@router.callback_query(F.data == "ui_stats")
async def ui_stats(cb: CallbackQuery):
    await cb.answer()
    await _show_stats(cb.message.chat.id, cb.message)

async def _create_game(chat_id: int, host_id: int, host_name: str, bot: Bot):
    SESSIONS[chat_id] = {
        "players": [],
        "hands": {},
        "answers": {},
        "scores": {},
        "host_idx": -1,
        "current_situation": None,
        "main_deck": [],
        "used_answers": [],
        "used_situations": []
    }
    
    # Добавляем ботов как игроков
    for bot_player in BOT_PLAYERS:
        SESSIONS[chat_id]["players"].append({
            "user_id": bot_player.bot_id,
            "username": bot_player.name,
            "is_bot": True,
            "bot_instance": bot_player
        })
        SESSIONS[chat_id]["scores"][bot_player.bot_id] = 0
    
    print(f"🤖 Добавлено ботов: {len(BOT_PLAYERS)}")

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer("Сначала нажмите «Начать игру».", reply_markup=main_menu())
        return
    
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились к игре! Ожидайте начала раунда.")
        except TelegramBadRequest as e:
            await feedback.answer(f"{user_name}, нажмите Start у бота и повторите. {e}")
            return
        st["players"].append({
            "user_id": user_id, 
            "username": user_name,
            "is_bot": False
        })
        st["scores"][user_id] = 0
    
    real_players = len([p for p in st["players"] if not p.get("is_bot", False)])
    bot_count = len([p for p in st["players"] if p.get("is_bot", False)])
    await feedback.answer(
        f"Игроков: {real_players} человек + {bot_count} ботов", 
        reply_markup=main_menu()
    )

async def _show_stats(chat_id: int, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st or not st["players"]:
        await feedback.answer("Игра не найдена или нет игроков.", reply_markup=main_menu())
        return
    
    sorted_players = sorted(
        st["players"], 
        key=lambda p: st["scores"].get(p["user_id"], 0), 
        reverse=True
    )
    
    lines = ["📊 **Статистика игры:**\n"]
    for i, p in enumerate(sorted_players, 1):
        score = st["scores"].get(p["user_id"], 0)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▪️"
        bot_mark = " 🤖" if p.get("is_bot", False) else ""
        lines.append(f"{medal} {i}. {p['username']}{bot_mark} — {score} очков")
    
    await feedback.answer("\n".join(lines), reply_markup=main_menu())

async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Нужно минимум 2 игрока.", reply_markup=main_menu())
        return

    st["answers"].clear()
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    host_id = host["user_id"]

    if "used_situations" not in st:
        st["used_situations"] = []
    
    all_situations = decks.get_all_situations()
    available_situations = [s for s in all_situations if s not in st["used_situations"]]
    
    if not available_situations:
        print("♻️ Все ситуации использованы! Сброс использованных ситуаций.")
        st["used_situations"] = []
        available_situations = all_situations
    
    st["current_situation"] = decks.get_random_from_list(available_situations)
    st["used_situations"].append(st["current_situation"])
    
    print(f"🎲 Выбрана ситуация: {st['current_situation']}")
    print(f"📊 Использовано ситуаций: {len(st['used_situations'])}/{len(all_situations)}")
    
    try:
        card_image = create_situation_card(st["current_situation"])
        photo = BufferedInputFile(card_image.read(), filename='situation.png')
        await bot.send_photo(
            chat_id,
            photo=photo,
            caption=f"🎮 **Новый раунд!**\nВедущий: {host['username']}"
        )
    except Exception as e:
        print(f"⚠️ Ошибка создания карточки: {e}")
        await bot.send_message(
            chat_id,
            f"🎮 **Новый раунд!**\nВедущий: {host['username']}\n\n📝 Ситуация:\n{st['current_situation']}"
        )

    cards_in_use = set(st["used_answers"])
    for uid, hand in st["hands"].items():
        cards_in_use.update(hand)
    
    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in cards_in_use]
    
    non_host_players = [p for p in st["players"] if p["user_id"] != host_id]
    if non_host_players:
        min_hand_size = min(len(st["hands"].get(p["user_id"], [])) for p in non_host_players)
        cards_needed = len(non_host_players) * (10 - min_hand_size)
    else:
        cards_needed = 0
    
    if len(st["main_deck"]) < cards_needed:
        print(f"⚠️ Карты закончились! Сброс used_answers. Было использовано: {len(st['used_answers'])}")
        st["used_answers"].clear()
        
        cards_in_hands = set()
        for uid, hand in st["hands"].items():
            cards_in_hands.update(hand)
        
        full_deck = decks.get_new_shuffled_answers_deck()
        st["main_deck"] = [c for c in full_deck if c not in cards_in_hands]

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        
        current_hand = st["hands"].get(uid, [])
        
        while len(current_hand) < 10 and st["main_deck"]:
            new_card = st["main_deck"].pop()
            if new_card not in current_hand:
                current_hand.append(new_card)
        
        st["hands"][uid] = current_hand
        print(f"✅ {'Бот' if p.get('is_bot') else 'Игрок'} {p['username']}: {len(current_hand)} карт в руке")

    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        
        hand = st["hands"].get(uid, [])
        
        if p.get("is_bot", False):
            asyncio.create_task(_bot_auto_answer(bot, chat_id, p, st["current_situation"], hand))
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{uid}:{i}")]
                for i, card in enumerate(hand)
            ])
            try:
                msg = f"📝 Ситуация:\n{st['current_situation']}\n\n🃏 Ваша рука ({len(hand)} карт).\nВыберите подходящий ответ:"
                await bot.send_message(uid, msg, reply_markup=kb)
            except TelegramBadRequest:
                await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}. Убедитесь, что бот запущен.")

async def _bot_auto_answer(bot: Bot, chat_id: int, bot_player_data: dict, situation: str, hand: list):
    """Автоматический ответ бота"""
    await asyncio.sleep(random.uniform(2, 5))
    
    st = SESSIONS.get(chat_id)
    if not st:
        return
    
    uid = bot_player_data["user_id"]
    
    if uid in st["answers"]:
        return
    
    bot_instance = bot_player_data.get("bot_instance")
    
    if bot_instance and hand:
        try:
            selected_answer = await bot_instance.generate_answer(situation, hand)
            idx = hand.index(selected_answer)
            
            st["answers"][uid] = {"card": selected_answer, "index": idx}
            print(f"🤖 Бот {bot_player_data['username']} выбрал: {selected_answer}")
            
            await _check_all_answered(bot, chat_id)
            
        except Exception as e:
            print(f"⚠️ Ошибка ответа бота: {e}")
            if hand:
                selected_answer = random.choice(hand)
                idx = hand.index(selected_answer)
                st["answers"][uid] = {"card": selected_answer, "index": idx}
                await _check_all_answered(bot, chat_id)

async def _check_all_answered(bot: Bot, chat_id: int):
    """Проверяет, ответили ли все игроки"""
    st = SESSIONS.get(chat_id)
    if not st:
        return
    
    host_id = st["players"][st["host_idx"]]["user_id"]
    need = len(st["players"]) - 1
    
    if len(st["answers"]) >= need:
        ordered = [(u, st["answers"][u]["card"]) for u in st["answers"]]
        lines, buttons = [], []
        for i, (u2, ans) in enumerate(ordered, 1):
            player_data = next(p for p in st["players"] if p["user_id"] == u2)
            name = player_data["username"]
            bot_mark = " 🤖" if player_data.get("is_bot", False) else ""
            lines.append(f"{i}. **{name}{bot_mark}** — _{ans}_")
            buttons.append([InlineKeyboardButton(text=f"{i}. {name}", callback_data=f"pick:{chat_id}:{i-1}")])
        
        await bot.send_message(
            chat_id, 
            "📋 **Ответы игроков:**\n\n" + "\n".join(lines) + "\n\n👆 Ведущий, выберите лучший ответ:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

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

    if uid in st["answers"]:
        await cb.answer("Вы уже выбрали ответ!", show_alert=True)
        return

    hand = st["hands"].get(uid, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    card = hand[idx]
    st["answers"][uid] = {"card": card, "index": idx}
    await cb.answer(f"✅ Вы выбрали: {card}")

    await _check_all_answered(cb.bot, group_chat_id)

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

    ordered = [(u, st["answers"][u]["card"]) for u in st["answers"]]
    if idx < 0 or idx >= len(ordered):
        await cb.answer("Неверный индекс.", show_alert=True)
        return

    win_uid, win_ans = ordered[idx]
    win_player_data = next(p for p in st["players"] if p["user_id"] == win_uid)
    win_name = win_player_data["username"]
    bot_mark = " 🤖" if win_player_data.get("is_bot", False) else ""

    st["scores"][win_uid] = st["scores"].get(win_uid, 0) + 1

    for uid, answer_data in st["answers"].items():
        hand = st["hands"].get(uid, [])
        card = answer_data["card"]
        
        if card in hand:
            hand.remove(card)
        
        st["used_answers"].append(card)
        st["hands"][uid] = hand

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    
    await cb.message.edit_text(
        f"🏆 **Победитель раунда:** {win_name}{bot_mark}\n💬 **Ответ:** _{win_ans}_\n\n⭐ Очков: {st['scores'][win_uid]}"
    )

    image_result, joke = await generate_card_content(st["current_situation"], win_ans)
    
    if image_result:
        try:
            if image_result.startswith('temp_image_') or os.path.isfile(image_result):
                photo = FSInputFile(image_result)
                await cb.bot.send_photo(
                    group_chat_id, 
                    photo=photo,
                    caption=f"😄 {joke or ''}"
                )
                try:
                    os.remove(image_result)
                    print(f"🗑️ Временный файл удален: {image_result}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить файл: {e}")
            else:
                await cb.bot.send_photo(group_chat_id, image_result, caption=f"😄 {joke or ''}")
        except Exception as e:
            print(f"⚠️ Ошибка отправки изображения: {e}")
            await cb.bot.send_message(group_chat_id, f"😄 **Шутка:** {joke or '—'}")
    else:
        await cb.bot.send_message(group_chat_id, f"😄 **Шутка:** {joke or '—'}")

    sorted_players = sorted(st["players"], key=lambda p: st["scores"].get(p["user_id"], 0), reverse=True)
    stats_lines = ["📊 **Текущий счёт:**"]
    for i, p in enumerate(sorted_players, 1):
        score = st["scores"].get(p["user_id"], 0)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▪️"
        bot_mark = " 🤖" if p.get("is_bot", False) else ""
        stats_lines.append(f"{medal} {p['username']}{bot_mark}: {score}")
    
    await cb.bot.send_message(group_chat_id, "\n".join(stats_lines) + "\n\n✅ Раунд завершён.", reply_markup=main_menu())
