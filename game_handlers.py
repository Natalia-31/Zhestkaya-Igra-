from aiogram import Dispatcher
from aiogram.types import Message

async def handle_join(message: Message):
    await message.answer("🔗 Вы присоединились к игре (заглушка).")

def register_game_handlers(dp: Dispatcher):
    dp.message.register(handle_join, commands={"join"})
