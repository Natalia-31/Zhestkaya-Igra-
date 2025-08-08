def register_game_handlers(dp):
    # пример простой команды
    @dp.message_handler(commands=["start"])
    async def start_command(message: types.Message):
        await message.answer("Привет! Жесткая игра начинается!")
# Game handlers placeholder
