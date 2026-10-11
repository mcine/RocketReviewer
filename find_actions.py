from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
img = Image.open(BASE_DIR / "strategy_tab_view2.png")
# Look in area x: 1200 to 1800, y: 450 to 580
action_crop = img.crop((1200, 440, 1750, 560))
action_crop.save(BASE_DIR / "action_buttons.png")
print("Saved action_buttons.png")
