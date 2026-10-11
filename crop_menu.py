from PIL import Image

img = Image.open(r"c:\misc\code\appautomation\strategy_tab_view.png")
print("Size:", img.size)

# Crop the left menu bar from x=0 to 80, y=0 to 300
crop = img.crop((0, 0, 80, 300))
crop.save(r"c:\misc\code\appautomation\left_menu.png")

# Let's inspect the green Tree icon vs Strategy icon
# Where is Tree icon?
# Where is Strategy icon?
# Let's find green pixels (the Tree button background)
for y in range(img.height):
    for x in range(80):
        r, g, b, a = img.getpixel((x, y))
        # Find the magnifying glass or text
        pass

print("Crop saved to left_menu.png")
