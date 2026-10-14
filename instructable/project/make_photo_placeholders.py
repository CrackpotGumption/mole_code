"""Create plain layout placeholders, not simulated build photographs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

dest = Path(__file__).parent / "photo_placeholders"
dest.mkdir(exist_ok=True)
items = [
    ("01_mechanism.png", "PHOTO TO ADD", "Removed target mechanism", "Show objects 6, 22, 10 and 15; captured nuts and fasteners."),
    ("02_sensor_mount.png", "PHOTO TO ADD", "Accelerometer and pin clearance", "Show the U-channel guard, sensor attachment and pin-clearance pocket."),
    ("03_moving_wiring.png", "PHOTO TO ADD", "Moving wire loop", "Show slack from the moving guard to the stationary terminal."),
    ("04_pneumatic_connections.png", "PHOTO TO ADD", "Valve and cylinder connections", "Show manifold, valve ports, exhaust controls and cylinder tubing."),
]
font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
title = ImageFont.truetype(font_path, 44)
label = ImageFont.truetype(font_path, 28)
small = ImageFont.truetype(font_path, 22)
for filename, eyebrow, heading, note in items:
    canvas = Image.new("RGB", (1400, 900), "#f3f4f5")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((40, 40, 1360, 860), outline="#b9bec3", width=3)
    draw.text((700, 310), eyebrow, font=label, fill="#697179", anchor="mm")
    draw.text((700, 405), heading, font=title, fill="#30363c", anchor="mm")
    draw.text((700, 500), note, font=small, fill="#59636c", anchor="mm")
    draw.text((700, 770), "DRAFT PLACEHOLDER — replace with an actual build photograph", font=small, fill="#697179", anchor="mm")
    canvas.save(dest / filename)
print("Created four labeled photo placeholders.")
