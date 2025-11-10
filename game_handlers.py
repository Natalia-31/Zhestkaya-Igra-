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

# Глобальные переменные для ботов
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
    WELCOME_VIDEO_PATH = "assets/welcome.mp4"
    try:
        if os.path.exists(WELCOME_VIDEO_PATH):
            video = FSInputFile(WELCOME_VIDEO_PATH)
            await m.bot.send_video(
                chat_id=m.chat.id,
                video=video,
                caption="🎮 Добро пожаловать в Жесткую Игру!\n\n"
                        "✨ Особенности:\n"
                        "• 2 бота-игрока: 🤖 БотИгрок1 и 🤖 БотИгрок2\n"
                        "• Боты могут быть игроками и ведущими\n"
                        "• Анонимные ответы для честной игры!"
            )
    except Exception as e:
        print(f"⚠️ Ошибка отправки видео: {e}")
    
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
        "used_situations": [],
        "shuffled_answers": [],
        "answers_with_authors": []
    }
    
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
    st["shuffled_answers"] = []
    st["answers_with_authors"] = []
    
    # Теперь боты тоже могут быть ведущими
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    host_id = host["user_id"]
    is_bot_host = host.get("is_bot", False)
    
    host_label = f"{host['username']} 🤖" if is_bot_host else host['username']
    print(f"👤 Ведущий: {host_label}")

    if "used_situations" not in st:
        st["used_situations"] = []
    
    all_situations = decks.get_all_situations()
    available_situations = [s for s in all_situations if s not in st["used_situations"]]
    
    if not available_situations:
        print("♻️ Все ситуации использованы! Сброс.")
        st["used_situations"] = []
        available_situations = all_situations
    
    st["current_situation"] = decks.get_random_from_list(available_situations)
    st["used_situations"].append(st["current_situation"])
    
    print(f"🎲 Ситуация: {st['current_situation']}")
    
    try:
        card_image = create_situation_card(st["current_situation"])
        photo = BufferedInputFile(card_image.read(), filename='situation.png')
        await bot.send_photo(
            chat_id,
            photo=photo,
            caption=f"🎮 **Новый раунд!**\nВедущий: {host_label}"
        )
    except Exception as e:
        print(f"⚠️ Ошибка создания карточки: {e}")
        await bot.send_message(
            chat_id,
            f"🎮 **Новый раунд!**\nВедущий: {host_label}\n\n📝 Ситуация:\n{st['current_situation']}"
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
        print(f"⚠️ Карты закончились! Сброс.")
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
        print(f"✅ {'Бот' if p.get('is_bot') else 'Игрок'} {p['username']}: {len(current_hand)} карт")

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
                msg = f"📝 Ситуация:\n{st['current_situation']}\n\n🃏 Ваша рука ({len(hand)} карт).\nВыберите ответ:"
                await bot.send_message(uid, msg, reply_markup=kb)
            except TelegramBadRequest:
                await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}.")

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
    
    host = st["players"][st["host_idx"]]
    host_id = host["user_id"]
    need = len(st["players"]) - 1
    
    if len(st["answers"]) >= need:
        # Перемешиваем ответы для анонимности
        ordered = [(u, st["answers"][u]["card"]) for u in st["answers"]]
        
        # Сохраняем оригинальный порядок с авторами
        st["answers_with_authors"] = ordered.copy()
        
        # Перемешиваем ответы
        shuffled_answers = [(u, card) for u, card in ordered]
        random.shuffle(shuffled_answers)
        
        # Сохраняем перемешанный порядок
        st["shuffled_answers"] = shuffled_answers
        
        # Формируем список БЕЗ имён
        lines, buttons = [], []
        for i, (uid, ans) in enumerate(shuffled_answers, 1):
            lines.append(f"{i}. _{ans}_")
            buttons.append([InlineKeyboardButton(
                text=f"{i}. Выбрать этот ответ", 
                callback_data=f"pick:{chat_id}:{i-1}"
            )])
        
        host_mark = " 🤖" if host.get("is_bot", False) else ""
        
        await bot.send_message(
            chat_id, 
            f"📋 **Ответы игроков (анонимно):**\n\n" + "\n".join(lines) + 
            f"\n\n🎭 Авторы ответов скрыты для честной игры!\n"
            f"👆 Ведущий {host['username']}{host_mark}, выберите лучший ответ:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        
        # Если ведущий - бот, запускаем автовыбор
        if host.get("is_bot", False):
            asyncio.create_task(_bot_host_choose_winner(bot, chat_id))

async def _bot_host_choose_winner(bot: Bot, chat_id: int):
    """Бот-ведущий автоматически выбирает победителя"""
    st = SESSIONS.get(chat_id)
    if not st:
        return
    
    host = st["players"][st["host_idx"]]
    if not host.get("is_bot", False):
        return
    
    bot_instance = host.get("bot_instance")
    if not bot_instance:
        return
    
    await asyncio.sleep(random.uniform(3, 6))
    
    shuffled_answers = st.get("shuffled_answers", [])
    
    # Формируем анонимный список для AI
    players_answers = [(f"Вариант {i+1}", answer) for i, (uid, answer) in enumerate(shuffled_answers)]
    
    try:
        winner_idx = await bot_instance.choose_winner(st["current_situation"], players_answers)
        await _process_winner(bot, chat_id, winner_idx)
    except Exception as e:
        print(f"⚠️ Ошибка выбора победителя ботом: {e}")
        winner_idx = random.randint(0, len(shuffled_answers) - 1)
        await _process_winner(bot, chat_id, winner_idx)

async def _process_winner(bot: Bot, chat_id: int, winner_idx: int):
    """Обрабатывает выбор победителя"""
    st = SESSIONS.get(chat_id)
    if not st:
        return
    
    shuffled_answers = st.get("shuffled_answers", [])
    
    if winner_idx < 0 or winner_idx >= len(shuffled_answers):
        return
    
    # Получаем победителя из перемешанного списка
    win_uid, win_ans = shuffled_answers[winner_idx]
    
    win_player_data = next(p for p in st["players"] if p["user_id"] == win_uid)
    win_name = win_player_data["username"]
    bot_mark = " 🤖" if win_player_data.get("is_bot", False) else ""
    
    host = st["players"][st["host_idx"]]
    host_mark = " 🤖" if host.get("is_bot", False) else ""

    st["scores"][win_uid] = st["scores"].get(win_uid, 0) + 1

    for uid, answer_data in st["answers"].items():
        hand = st["hands"].get(uid, [])
        card = answer_data["card"]
        if card in hand:
            hand.remove(card)
        st["used_answers"].append(card)
        st["hands"][uid] = hand
    
    # Показываем всех игроков и их ответы после выбора
    reveal_lines = ["🎭 **Раскрытие ответов:**\n"]
    for uid, answer in shuffled_answers:
        player_data = next(p for p in st["players"] if p["user_id"] == uid)
        player_mark = " 🤖" if player_data.get("is_bot", False) else ""
        winner_emoji = "🏆 " if uid == win_uid else "▪️ "
        reveal_lines.append(f"{winner_emoji}**{player_data['username']}{player_mark}:** _{answer}_")
    
    await bot.send_message(chat_id, "\n".join(reveal_lines))
    
    await bot.send_message(
        chat_id,
        f"🏆 **Победитель раунда:** {win_name}{bot_mark}\n"
        f"👤 **Выбрал:** {host['username']}{host_mark}\n"
        f"💬 **Победный ответ:** _{win_ans}_\n\n"
        f"⭐ Очков: {st['scores'][win_uid]}"
    )

    image_result, joke = await generate_card_content(st["current_situation"], win_ans)
    
    if image_result:
        try:
            if image_result.startswith('temp_image_') or os.path.isfile(image_result):
                photo = FSInputFile(image_result)
                await bot.send_photo(chat_id, photo=photo, caption=f"😄 {joke or ''}")
                try:
                    os.remove(
