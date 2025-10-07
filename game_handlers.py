# handlers/game_handlers.py
import asyncio
import os
from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, generate_card_content
from card_generator import create_situation_card

router = Router()
SESSIONS: Dict[int, Dict[str, Any]] = {}

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="Новый раунд", callback_data="ui_start_round")],
        [InlineKeyboardButton(text="Статистика", callback_data="ui_stats")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню.", reply_markup=main_menu())

@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer("Игра начата!", reply_markup=main_menu())

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
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name)
    await cb.answer()
    try:
        await cb.message.edit_text("Игра начата!", reply_markup=main_menu())
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

async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],
        "hands": {},
        "answers": {},
        "scores": {},
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
            await feedback.answer(f"{user_name}, нажмите Start у бота и повторите. {e}")
            return
        st["players"].append({"user_id": user_id, "username": user_name})
        st["scores"][user_id] = 0
    await feedback.answer(f"Игроков: {len(st['players'])}", reply_markup=main_menu())

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
        lines.append(f"{medal} {i}. {p['username']} — {score} очков")
    
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

    st["current_situation"] = decks.get_random_situation()
    
    # Отправляем карточку вместо текста
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

    # УЛУЧШЕНО: Собираем все карты, которые уже где-то используются
    cards_in_use = set(st["used_answers"])  # Использованные карты
    for uid, hand in st["hands"].items():
        cards_in_use.update(hand)  # Карты в руках игроков
    
    # Создаем колоду без карт, которые уже в игре
    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [c for c in full_deck if c not in cards_in_use]
    
    # Подсчитываем сколько карт нужно
    non_host_players = [p for p in st["players"] if p["user_id"] != host_id]
    if non_host_players:
        min_hand_size = min(len(st["hands"].get(p["user_id"], [])) for p in non_host_players)
        cards_needed = len(non_host_players) * (10 - min_hand_size)
    else:
        cards_needed = 0
    
    # Если доступных карт мало, сбрасываем used_answers
    if len(st["main_deck"]) < cards_needed:
        print(f"⚠️ Карты закончились! Сброс used_answers. Было использовано: {len(st['used_answers'])}")
        st["used_answers"].clear()
        
        # Пересоздаем колоду, исключая только карты в руках
        cards_in_hands = set()
        for uid, hand in st["hands"].items():
            cards_in_hands.update(hand)
        
        full_deck = decks.get_new_shuffled_answers_deck()
        st["main_deck"] = [c for c in full_deck if c not in cards_in_hands]

    # Добираем карты до 10 каждому игроку (кроме ведущего)
    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        
        # Берём текущую руку игрока
        current_hand = st["hands"].get(uid, [])
        
        # Добираем карты до 10
        while len(current_hand) < 10 and st["main_deck"]:
            new_card = st["main_deck"].pop()
            # ПРОВЕРКА: убеждаемся что карты нет в руке
            if new_card not in current_hand:
                current_hand.append(new_card)
        
        st["hands"][uid] = current_hand
        print(f"✅ Игрок {p['username']}: {len(current_hand)} карт в руке")

    # Отправка ситуации и карт в личку игрокам
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
            msg = f"📝 Ситуация:\n{st['current_situation']}\n\n🃏 Ваша рука ({len(hand)} карт).\nВыберите подходящий ответ:"
            await bot.send_message(uid, msg, reply_markup=kb)
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}. Убедитесь, что бот запущен.")

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

    need = len(st["players"]) - 1
    if len(st["answers"]) >= need:
        ordered = [(u, st["answers"][u]["card"]) for u in st["answers"]]
        lines, buttons = [], []
        for i, (u2, ans) in enumerate(ordered, 1):
            name = next(p["username"] for p in st["players"] if p["user_id"] == u2)
            lines.append(f"{i}. **{name}** — _{ans}_")
            buttons.append([InlineKeyboardButton(text=f"{i}. {name}", callback_data=f"pick:{group_chat_id}:{i-1}")])
        
        await cb.bot.send_message(
            group_chat_id, 
            "📋 **Ответы игроков:**\n\n" + "\n".join(lines) + "\n\n👆 Ведущий, выберите лучший ответ:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

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
    win_name = next(p["username"] for p in st["players"] if p["user_id"] == win_uid)

    # Начисление очка победителю
    st["scores"][win_uid] = st["scores"].get(win_uid, 0) + 1

    # Удаление использованной карты и добавление в used_answers
    for uid, answer_data in st["answers"].items():
        hand = st["hands"].get(uid, [])
        card = answer_data["card"]
        
        # Удаляем использованную карту из руки
        if card in hand:
            hand.remove(card)
        
        # Добавляем карту в использованные
        st["used_answers"].append(card)
        
        # Обновляем руку
        st["hands"][uid] = hand

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    
    await cb.message.edit_text(
        f"🏆 **Победитель раунда:** {win_name}\n💬 **Ответ:** _{win_ans}_\n\n⭐ Очков: {st['scores'][win_uid]}"
    )

    # ====== ОБНОВЛЕНО: Генерация шутки и картинки ======
    image_result, joke = await generate_card_content(st["current_situation"], win_ans)
    
    if image_result:
        try:
            # Проверяем - это локальный файл или URL
            if image_result.startswith('temp_image_') or os.path.isfile(image_result):
                # Локальный файл от Gemini
                print(f"📤 Отправляем локальный файл: {image_result}")
                photo = FSInputFile(image_result)
                await cb.bot.send_photo(
                    group_chat_id, 
                    photo=photo,
                    caption=f"😄 {joke or ''}"
                )
                # Удаляем временный файл
                try:
                    os.remove(image_result)
                    print(f"🗑️ Временный файл удален: {image_result}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить файл: {e}")
            else:
                # URL от Pollinations
                print(f"📤 Отправляем URL: {image_result}")
                await cb.bot.send_photo(group_chat_id, image_result, caption=f"😄 {joke or ''}")
        except Exception as e:
            print(f"⚠️ Ошибка отправки изображения: {e}")
            await cb.bot.send_message(group_chat_id, f"😄 **Шутка:** {joke or '—'}")
    else:
        # Только шутка без картинки
        await cb.bot.send_message(group_chat_id, f"😄 **Шутка:** {joke or '—'}")

    # Показать текущую статистику
    sorted_players = sorted(st["players"], key=lambda p: st["scores"].get(p["user_id"], 0), reverse=True)
    stats_lines = ["📊 **Текущий счёт:**"]
    for i, p in enumerate(sorted_players, 1):
        score = st["scores"].get(p["user_id"], 0)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▪️"
        stats_lines.append(f"{medal} {p['username']}: {score}")
    
    await cb.bot.send_message(group_chat_id, "\n".join(stats_lines) + "\n\n✅ Раунд завершён.", reply_markup=main_menu())
