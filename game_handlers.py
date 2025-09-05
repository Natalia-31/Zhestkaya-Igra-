from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("join"))
async def handle_join(message: Message):
    await message.answer("➕ Вы присоединились к игре (заглушка).")

@router.message(Command("start"))
async def handle_start(message: Message):
    await message.answer("❗️ Бот работает. Нажмите /join чтобы присоединиться к игре.")

def register_game_handlers(dp):
    dp.include_router(router)
