# handlers/game_handlers.py — игровой роутер и кнопки

from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# ВАЖНО: импортируем только из game_utils, чтобы не создать цикл
from game_utils import decks, gen  # колоды и генератор

# Глобальное хранилище состояния игр по чату
# Структура заполняется при /newgame
game_states: Dict[int, Dict[str, Any]] = {}

router = Router()

# ========== ВСПОМОГАТЕЛЬНЫЕ КНОПКИ ==========

def main_menu_kb(is_host: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🆕 Начать игру", callback_data="ui_newgame")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join")],
    ]
    if is_host:
        buttons.append([InlineKeyboardButton(text="🎬 Новый раунд", callback_data="ui_round")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== КОМАНДЫ ==========

@router.message(Command("start"))
async def cmd_start(message: Message):
    # Показываем меню с кнопками; ведущим станет тот, кто потом нажмет "Начать игру"
    is_host = False
    await message.answer(
        "Добро пожаловать в Жесткую Игру!\nВыберите действие кнопкой ниже.",
        reply_markup=main_menu_kb(is_host)
    )

@router.message(Command("newgame"))
async def cmd_newgame(message: Message):
    # Альтернативный запуск через команду (для удобства)
    await _create_new_game(message, host_id=message.from_user.id, host_name=message.from_user.first_name)

@router.message(Command("join"))
async def cmd_join(message: Message, bot: Bot):
    # Альтернативное присоединение через команду
    await _join_flow(message.chat.id, message.from_user.id, message.from_user.first_name, bot, feedback_message=message)

@router.message(Command("round"))
async def cmd_round(message: Message, bot: Bot):
    # Альтернативный запуск раунда через команду
    await _start_round_flow(message.chat.id, message.from_user.id, bot, message)

# ========== ИНЛАЙН-КНОПКИ И МЕНЮ ==========

@router.callback_query(F.data == "ui_newgame")
async def ui_newgame(cb: CallbackQuery):
    await _create_new_game(cb.message, host_id=cb.from_user.id, host_name=cb.from_user.first_name)
    await cb.answer()

@router.callback_query(F.data == "ui_join")
async def ui_join(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.first_name, bot, feedback_message=cb.message)
    await cb.answer()

@router.callback_query(F.data == "ui_round")
async def ui_round(cb: CallbackQuery, bot: Bot):
    await _start_round_flow(cb.message.chat.id, cb.from_user.id, bot, cb.message)
    await cb.answer()

# ========== ЛОГИКА СОЗДАНИЯ/ПРИСОЕДИНЕНИЯ/РАУНДА ==========

async def _create_new_game(anchor_message: Message, host_id: int, host_name: str):
    chat_id = anchor_message.chat.id
    # Если игра уже активна — перезатираем для простоты
    game_states[chat_id] = {
        "is_active": True,
        "host_id": host_id,
        "host_name": host_name,
        "players": {},           # {user_id: {"name": str, "hand": list[str], "score": int}}
        "main_deck": decks.get_new_shuffled_answers_deck(),
        "current_situation": None,
        "played_in_round": set(),  # user_id, которые уже отправили ответ
    }
    await anchor_message.answer(
        f"🎉 Игра создана! Ведущий: {host_name}\nНажмите “Присоединиться”, затем ведущий запускает раунд.",
        reply_markup=main_menu_kb(is_host=True)
    )

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback_message: Message):
    state = game_states.get(chat_id)
    if not state or not state.get("is_active"):
        await feedback_message.answer("Игра пока не создана. Нажмите “Начать игру”.")
        return

    if user_id in state["players"]:
        await feedback_message.answer(f"{user_name}, вы уже в игре.")
        return

    # Пытаемся написать в личку, чтобы потом можно было раздавать карты
    try:
        await bot.send_message(user_id, "Вы присоединились к игре! Ожидайте начала раунда.")
    except TelegramBadRequest:
        await feedback_message.answer(
            f"⚠️ {user_name}, разрешите боту писать в личку (нажмите Start у бота), затем снова нажмите “Присоединиться”."
        )
        return

    state["players"][user_id] = {"name": user_name, "hand": [], "score": 0}
    await feedback_message.answer(f"✅ {user_name} присоединился к игре!")

async def _start_round_flow(chat_id: int, actor_id: int, bot: Bot, feedback_message: Message):
    state = game_states.get(chat_id)
    if not state or not state.get("is_active"):
        await feedback_message.answer("Игра не создана. Нажмите “Начать игру”.")
        return

    if actor_id != state["host_id"]:
        await feedback_message.answer("Только ведущий может начинать новый раунд.")
        return

    # Раздача/добор до 10 карт каждому
    state["played_in_round"] = set()
    for pid, pdata in state["players"].items():
        while len(pdata["hand"]) < 10:
            if not state["main_deck"]:
                state["main_deck"] = decks.get_new_shuffled_answers_deck()
            pdata["hand"].append(state["main_deck"].pop())

    # Публикуем ситуацию
    situation = decks.get_random_situation()
    state["current_situation"] = situation
    await feedback_message.answer(f"‼️ Ситуация:\n\n`{situation}`", parse_mode="Markdown")

    # Отправляем каждому игроку в личку его 10 карт кнопками
    for pid, pdata in state["players"].items():
        # Каждая карта — отдельная кнопка (в одну колонку, чтобы не резало длинные тексты)
        buttons = [
            [InlineKeyboardButton(text=card, callback_data=f"play_answer|{chat_id}|{card[:60]}")]
            for card in pdata["hand"]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await bot.send_message(pid, "Ваши карты. Выберите ответ на ситуацию:", reply_markup=kb)
        except TelegramBadRequest:
            # Если писать в личку нельзя — пропускаем игрока
            continue

# ========== ОБРАБОТКА ХОДА ИГРОКА (ЛИЧКА) ==========

@router.callback_query(F.data.startswith("play_answer|"))
async def handle_play_answer(cb: CallbackQuery, bot: Bot):
    # Формат: play_answer|<chat_id>|<answer_prefix>
    try:
        _, chat_id_str, answer_prefix = cb.data.split("|", 2)
        chat_id = int(chat_id_str)
    except Exception:
        await cb.answer("Некорректные данные.")
        return

    state = game_states.get(chat_id)
    if not state or not state.get("is_active"):
        await cb.answer("Игра не активна.", show_alert=True)
        return

    user_id = cb.from_user.id
    if user_id not in state["players"]:
        await cb.answer("Вы не в этой игре.", show_alert=True)
        return

    if user_id in state["played_in_round"]:
        await cb.answer("Ход уже сделан в этом раунде.", show_alert=True)
        return

    # Найдем точную карту по префиксу (вдруг длинные тексты)
    hand = state["players"][user_id]["hand"]
    # Ищем первое совпадение по началу строки
    answer_full = next((c for c in hand if c.startswith(answer_prefix)), None)
    if not answer_full:
        # На крайний случай — берем точный префикс как ответ
        answer_full = answer_prefix

    # Публикуем в общий чат карточку-ответ как кнопку, ЖМЕТ ТОЛЬКО ВЕДУЩИЙ
    btn = InlineKeyboardButton(
        text=answer_full,
        callback_data=f"select_winner|{chat_id}|{user_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn]])
    await bot.send_message(chat_id, f"Ответ от игрока {cb.from_user.first_name}:", reply_markup=kb)

    # Удаляем карту из руки и отмечаем ход
    if answer_full in hand:
        hand.remove(answer_full)
    state["played_in_round"].add(user_id)

    # Фиксируем в уведомлении игроку
    try:
        await cb.message.edit_text("Ваш ответ отправлен в общий чат!")
    except TelegramBadRequest:
        pass
    await cb.answer()

# ========== ВЫБОР ПОБЕДИТЕЛЯ ВЕДУЩИМ ==========

@router.callback_query(F.data.startswith("select_winner|"))
async def handle_select_winner(cb: CallbackQuery, bot: Bot):
    # Формат: select_winner|<chat_id>|<winner_user_id>
    try:
        _, chat_id_str, winner_id_str = cb.data.split("|", 2)
        chat_id = int(chat_id_str)
        winner_id = int(winner_id_str)
    except Exception:
        await cb.answer("Некорректные данные.", show_alert=True)
        return

    state = game_states.get(chat_id)
    if not state or not state.get("is_active"):
        await cb.answer("Игра не активна.", show_alert=True)
        return

    if cb.from_user.id != state["host_id"]:
        await cb.answer("Только ведущий может выбирать победителя!", show_alert=True)
        return

    situation = state.get("current_situation")
    if not situation:
        await cb.answer("Ситуация не найдена для этого раунда.", show_alert=True)
        return

    # Извлекаем выбранный ответ прямо с кнопки сообщения (ее текст = ответ)
    try:
        winning_answer = cb.message.reply_markup.inline_keyboard.text
    except Exception:
        winning_answer = "Ответ недоступен"

    winner_name = state["players"].get(winner_id, {}).get("name", "Игрок")
    state["players"].setdefault(winner_id, {"name": winner_name, "hand": [], "score": 0})
    state["players"][winner_id]["score"] += 1

    # Убираем кнопки у нажатого сообщения
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await cb.answer(f"Победитель: {winner_name}")
    await bot.send_message(chat_id, f"🏆 Победитель раунда — {winner_name}!\nЕго ответ: “{winning_answer}”")

    # Генерация изображения по ситуации и ответу
    await bot.send_message(chat_id, "Генерирую изображение по победившему ответу…")
    await gen.send_illustration(bot, chat_id, situation, winning_answer)

    # Добор по 1 карте в личку
    for pid, pdata in state["players"].items():
        if "hand" not in pdata:
            pdata["hand"] = []
        if not state["main_deck"]:
            state["main_deck"] = decks.get_new_shuffled_answers_deck()
        new_card = state["main_deck"].pop()
        pdata["hand"].append(new_card)
        try:
            await bot.send_message(pid, f"Вы добрали карту: `{new_card}`", parse_mode="Markdown")
        except TelegramBadRequest:
            continue

    # Готово, раунд завершён
    state["current_situation"] = None
    await bot.send_message(chat_id, "Раунд завершён. Ведущий, начните следующий раунд кнопкой “Новый раунд”.")
