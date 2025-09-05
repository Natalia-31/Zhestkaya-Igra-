from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("join"))
async def handle_join(message: Message):
    await message.answer("➕ Вы присоединились к игре (заглушка).")

@router.message(Command("start"))
async def handle_start(message: Message):
    await message.answer("Бот работает! Используй /join чтобы присоединиться к игре.")

# (оставьте echo, если нужно отладить любую активность)
@router.message()
async def echo(message: Message):
    await message.answer(f"DEBUG: Ты написал: {message.text}")

def register_game_handlers(dp):
    dp.include_router(router)
