# Замените только этот метод в файле game_utils.py

async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
    if answer:
        # 1. Переводим русский сюжет на английский
        russian_subject = situation.replace("____", answer)
        try:
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(None, self.translator.translate, russian_subject, "en")
            english_subject = translated.text
        except Exception as e:
            print(f"❌ Ошибка перевода: {e}. Используем русский текст.")
            english_subject = russian_subject

        # 2. Формируем "перевернутый" промпт
        # СНАЧАЛА стиль, ПОТОМ сюжет
        style_keywords = "A photorealistic, 8k resolution, cinematic photo of"
        prompt = f"{style_keywords} {english_subject}"

    else:
        prompt = f"A photorealistic photo of {situation}"

    image_bytes_io = await self.generate_image_from_prompt(prompt)

    if image_bytes_io:
        await bot.send_photo(
            chat_id,
            photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
            caption=f"Промпт: {prompt}"
        )
        return True

    await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Похоже, музы взяли выходной.")
    return False
