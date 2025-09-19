import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8012894305:AAEV10lG4T_4qHgj0WbJJnBdWPOgPXnHBXs"

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="ui_scores")]
    ])

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    @dp.message()
    async def any_msg(message: types.Message):
        await message.answer("Тестовое меню:", reply_markup=main_menu())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
