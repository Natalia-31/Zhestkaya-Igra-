import openai
from config import IMAGE_SETTINGS

async def generate_image(situation: str, answer: str) -> str:
    if not IMAGE_SETTINGS["enabled"] or not IMAGE_SETTINGS["dalle_api_key"]:
        return ""

    prompt = f"{situation.strip()} {answer.strip()}"
    openai.api_key = IMAGE_SETTINGS["dalle_api_key"]

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size=IMAGE_SETTINGS.get("image_size", "512x512")
        )
        return response['data'][0]['url']
    except Exception as e:
        print(f"[Image Generator Error] {e}")
        return ""
