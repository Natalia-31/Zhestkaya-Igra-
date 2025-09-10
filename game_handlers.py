from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from game_utils import send_random_situation_with_image, get_random_situation

router = Router()

# Клавиатура с основными действиями
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Начать игру", callback_data="new_game"),
                InlineKeyboardButton(text="➕ Присоединиться", callback_data="join_game"),
                InlineKeyboardButton(text="🎲 Новый раунд", callback_data="start_round"),
            ]
        ]
    )

# Стартовая команда
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🎮 **Жесткая Игра**\n\n"
        "Выберите действие кнопкой или командой:\n"
        "/new_game — начать игру\n"
        "/join_game — присоединиться к игре\n"
        "/start_round — запустить новый раунд",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

# /new_game
@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    # Здесь инициализируйте новую игру: очищайте состояние, список игроков и т.п.
    # Для примера просто отправляем ответ.
    await message.answer("✅ Игра начата! Ждём, пока игроки присоединятся.", reply_markup=main_menu_kb())

@router.callback_query(F.data == "new_game")
async def cb_new_game(callback: CallbackQuery):
    await callback.answer("Игра начата!", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=main_menu_kb())

# /join_game
@router.message(Command("join_game"))
async def cmd_join_game(message: Message):
    user = message.from_user.full_name or message.from_user.username
    # Добавьте логику: сохраните пользователя в список игроков
    await message.answer(f"➕ **{user}** присоединился к игре!", parse_mode="Markdown", reply_markup=main_menu_kb())

@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery):
    user = callback.from_user.full_name or callback.from_user.username
    await callback.answer(show_alert=False)
    await callback.message.answer(f"➕ **{user}** присоединился к игре!", parse_mode="Markdown")

# /start_round
@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    host = message.from_user.full_name or message.from_user.username
    await message.answer(
        f"🎬 **Раунд запущен!**\n👑 **Ведущий:** {host}",
        parse_mode="Markdown"
    )
    ok = await send_random_situation_with_image(message.bot, message.chat.id)
    if ok:
        await message.answer("✅ Ситуация и изображение отправлены!", parse_mode="Markdown")
    else:
        await message.answer("⚠️ Ситуация без изображения отправлена.", parse_mode="Markdown")

@router.callback_query(F.data == "start_round")
async def cb_start_round(callback: CallbackQuery):
    host = callback.from_user.full_name or callback.from_user.username
    await callback.answer(show_alert=False)
    await callback.message.answer(
        f"🎬 **Раунд запущен!**\n👑 **Ведущий:** {host}",
        parse_mode="Markdown"
    )
    ok = await send_random_situation_with_image(callback.bot, callback.message.chat.id)
    if ok:
        await callback.message.answer("✅ Ситуация и изображение отправлены!", parse_mode="Markdown")
    else:
        await callback.message.answer("⚠️ Ситуация без изображения отправлена.", parse_mode="Markdown")

# Текстовые команды в чате без кнопок
@router.message()
async def unknown(message: Message):
    await message.answer(
        "Неизвестная команда.\n"
        "Используйте /new_game, /join_game или /start_round.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
