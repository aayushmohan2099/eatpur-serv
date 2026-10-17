import random
import string
import io
import base64
from PIL import Image, ImageDraw, ImageFont


def generate_captcha_image(text: str) -> str:
    width, height = 300, 80
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # ✅ Use bold font (same as your example)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 48
        )
    except:
        font = ImageFont.load_default()

    # ✅ CENTER TEXT PROPERLY (better than fixed 60,15)
    text_width = draw.textlength(text, font=font)
    x = (width - text_width) // 2
    y = (height - 48) // 2

    draw.text((x, y), text, fill=(0, 0, 0), font=font)

    # ✅ SAME NOISE STYLE (light lines)
    for _ in range(5):
        draw.line(
            (
                random.randint(0, width),
                random.randint(0, height),
                random.randint(0, width),
                random.randint(0, height),
            ),
            fill=(0, 0, 0),
            width=1,
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode()