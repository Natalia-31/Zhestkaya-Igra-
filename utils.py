--- game_utils.py
+++ game_utils.py
@@
 from dotenv import load_dotenv
 from aiogram import Bot
 from aiogram.types import BufferedInputFile
+import openai
+from config import OPENAI_API_KEY, OPENAI_SETTINGS
@@
 load_dotenv()
 NANO_API_KEY   = os.getenv("NANO_API_KEY")
 HORDE_API_KEY  = os.getenv("HORDE_API_KEY")
 POLLO_API_KEY  = os.getenv("POLLO_API_KEY")
+
+# Инициализация OpenAI
+openai.api_key = OPENAI_API_KEY
@@ class GameImageGenerator:
     async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
         if not answer:
             await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
             return False
-        prompt = create_prompt(situation, answer)
-        img = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)
+        prompt = create_prompt(situation, answer)
+        # Сначала пробуем OpenAI Image API
+        try:
+            img_resp = await openai.Image.acreate(
+                prompt=prompt,
+                n=1,
+                size="512x512"
+            )
+            img_data = await aiohttp.ClientSession().get(img_resp.data[0].url)
+            img_bytes = await img_data.read()
+            img = BytesIO(img_bytes)
+        except Exception:
+            # fallback на существующие сервисы
+            img = await self._try_pollinations(prompt) or await self._try_nanobanana(prompt)
 
         if not img:
             await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
             return False
@@ class GameVideoGenerator:
     async def send_video_illustration(self, bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
         prompt = create_video_prompt(situation, answer)
+        # Попытка через OpenAI (если в будущем будет поддержка видео)
+        # (оставляем основной PollO.ai fallback)
         url = await self._try_pollo_video(prompt)
