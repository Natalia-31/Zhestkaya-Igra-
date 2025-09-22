--- main.py
+++ main.py
@@
 import asyncio
 import logging
 import os
+
+from dotenv import load_dotenv
 
 from aiogram import Bot, Dispatcher
 from aiogram.fsm.storage.memory import MemoryStorage
 from aiogram.client.default import DefaultBotProperties
+
+import openai
+from config import OPENAI_API_KEY, OPENAI_SETTINGS
 
 from handlers.game_handlers import router as game_router
@@
 async def main():
-    if not BOT_TOKEN:
-        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
+    load_dotenv()
+    if not BOT_TOKEN:
+        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
+    if not OPENAI_API_KEY:
+        raise RuntimeError("OPENAI_API_KEY не задан в переменных окружения")
+
+    # Инициализация OpenAI
+    openai.api_key = OPENAI_API_KEY
+    # Если используете клиент OpenAI v1:
+    # from openai import OpenAI
+    # client = OpenAI(api_key=OPENAI_API_KEY)
 
     bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
     dp = Dispatcher(storage=MemoryStorage())
@@
     dp.include_router(game_router)
 
     await dp.start_polling(bot)
