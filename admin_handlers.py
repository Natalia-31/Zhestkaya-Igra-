from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("admin"))
async def handle_admin(message: Message):
    await message.answer("Это административная команда.")

def register_admin_handlers(dp):
    dp.include_router(router)
