import  gemeni

GEMENI_API_KEY = "AIzaSyDbtW1LxZGHqcEcPhIWVcr8wHa3nVQ5Jjw"  # Не выкладывайте открыто!

async def generate_image(prompt):
    gemeni.api_key = GEMENI_API_KEY
    response =  gemeni.Image.create(
        prompt=prompt,
        n=1,
        size="512x512"
    )
    image_url = response["data"][0]["url"]
    return image_url
