from pathlib import Path
from PIL import Image

img = Image.open(Path(__file__).resolve().parent / "strategy_tab_view2.png")
# Scan lower right: x from 1400 to 1800, y from 1000 to 1350
bu_ev_pixels = []
for y in range(1000, 1350):
    for x in range(1400, 1800):
        r, g, b, a = img.getpixel((x, y))
        if g > 150 and g > r * 2 and g > b * 1.2:
            bu_ev_pixels.append((x, y))

if bu_ev_pixels:
    min_x = min(p[0] for p in bu_ev_pixels)
    max_x = max(p[0] for p in bu_ev_pixels)
    min_y = min(p[1] for p in bu_ev_pixels)
    max_y = max(p[1] for p in bu_ev_pixels)
    print(f"BU EV button: X [{min_x}, {max_x}], Y [{min_y}, {max_y}]")
    print(f"Center: ({(min_x + max_x)//2}, {(min_y + max_y)//2})")
