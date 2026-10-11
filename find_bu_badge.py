from PIL import Image

img = Image.open(r"c:\misc\code\appautomation\table_crop.png")
# BU badge is green: find green pixels in table_crop
bu_pixels = []
for y in range(img.height):
    for x in range(img.width):
        r, g, b, a = img.getpixel((x, y))
        # Green BU badge: r is low, g is high, b is moderate
        if g > 150 and g > r * 2 and g > b * 1.2:
            bu_pixels.append((x, y))

if bu_pixels:
    min_x = min(p[0] for p in bu_pixels)
    max_x = max(p[0] for p in bu_pixels)
    min_y = min(p[1] for p in bu_pixels)
    max_y = max(p[1] for p in bu_pixels)
    print(f"BU badge in table_crop: X [{min_x}, {max_x}], Y [{min_y}, {max_y}]")
    center_x = 1200 + (min_x + max_x) // 2
    center_y = 100 + (min_y + max_y) // 2
    print(f"Absolute window coords: ({center_x}, {center_y})")
