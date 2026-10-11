from PIL import Image

img = Image.open(r"c:\misc\code\appautomation\left_menu.png")
# Let's inspect rows around y=180 to 280
green_pixels = []
for y in range(160, 300):
    for x in range(img.width):
        r, g, b, a = img.getpixel((x, y))
        # Strategy icon is teal/green: g > 100, g > r * 1.5, g > b * 1.2
        if g > 100 and g > r * 1.5 and g > b:
            green_pixels.append((x, y))

if green_pixels:
    min_x = min(p[0] for p in green_pixels)
    max_x = max(p[0] for p in green_pixels)
    min_y = min(p[1] for p in green_pixels)
    max_y = max(p[1] for p in green_pixels)
    print(f"Strategy icon/text bounds: X [{min_x}, {max_x}], Y [{min_y}, {max_y}]")
    print(f"Center: X = {(min_x + max_x)//2}, Y = {(min_y + max_y)//2}")
