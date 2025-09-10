import openai
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")   # ключ загрузится из перем. окружения

async def generate_image(prompt):
    openai.api_key = OPENAI_API_KEY
    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="512x512"
    )
    image_url = response["data"][0]["url"]
    return image_url
