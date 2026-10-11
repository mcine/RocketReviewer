from PIL import Image

img = Image.open(r"c:\misc\code\appautomation\strategy_tab_view2.png")
# Look in area x: 1200 to 1800, y: 450 to 580
action_crop = img.crop((1200, 440, 1750, 560))
action_crop.save(r"c:\misc\code\appautomation\action_buttons.png")
print("Saved action_buttons.png")
