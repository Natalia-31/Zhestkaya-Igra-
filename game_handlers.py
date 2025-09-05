from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message(commands=["join"])
async def handle_join(message: Message):
    await message.answer("➕ Вы присоединились к игре (заглушка).")

def register_game_handlers(dp):
    dp.include_router(router)
