from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message()
async def echo(message: Message):
    await message.answer(f"DEBUG: Ты написал: {message.text}")

def register_game_handlers(dp):
    dp.include_router(router)
