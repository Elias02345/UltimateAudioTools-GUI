"""Generate the app's original geometric waveform mark, not a third-party logo."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "apps/desktop/src-tauri/icons"
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGBA", (1024, 1024), (23, 25, 24, 255))
draw = ImageDraw.Draw(image)
for i, height in enumerate([150, 300, 480, 660, 400, 240]):
    x = 210 + i * 105
    draw.rounded_rectangle(
        (x, 512 - height // 2, x + 58, 512 + height // 2), radius=29, fill=(170, 204, 149, 255)
    )
image.save(root / "icon.png")
image.save(root / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
image.save(root / "icon.icns")
for size in [32, 128, 256]:
    image.resize((size, size), Image.Resampling.LANCZOS).save(root / f"{size}x{size}.png")
