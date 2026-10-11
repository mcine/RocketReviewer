from PIL import Image

img = Image.open(r"c:\misc\code\appautomation\strategy_tab_view2.png")

# Let's crop the poker table area:
# Table is roughly x: 1200 to 1800, y: 100 to 500
table_crop = img.crop((1200, 100, 1850, 500))
table_crop.save(r"c:\misc\code\appautomation\table_crop.png")

# Let's crop the bottom right EV buttons area:
# x: 1200 to 1700, y: 800 to 950
ev_crop = img.crop((1200, 800, 1750, 960))
ev_crop.save(r"c:\misc\code\appautomation\ev_crop.png")

# Also let's crop the hand tree navigation or action buttons below the table:
# < Back, Fold, Raise 2.3 bb
actions_crop = img.crop((1200, 360, 1800, 480))
actions_crop.save(r"c:\misc\code\appautomation\actions_crop.png")

print("Cropped areas saved.")
