# server.py
from flask import Flask, request, send_file
from diffusers import StableDiffusionPipeline
import torch
import os

app = Flask(__name__)

# Загружаем модель один раз при старте сервиса
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16
).to("cuda" if torch.cuda.is_available() else "cpu")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    prompt = data.get("prompt", "")
    # Генерация и сохранение в папку generated_images
    img = pipe(prompt).images[0]
    os.makedirs("generated_images", exist_ok=True)
    path = os.path.join("generated_images", "latest.png")
    img.save(path)
    return send_file(path, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
