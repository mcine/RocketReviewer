import sys
from pathlib import Path
sys.path.insert(0, r"C:\misc\code\rangegame")
from hand_replayer import parse_hand_file

coin_file = Path(r"C:\misc\code\rangegame\input\CoinPoker_Sharkendahl_2026-06-14_to_2026-06-15_Cash.txt")
if coin_file.exists():
    try:
        hands = parse_hand_file(coin_file)
        print(f"CoinPoker parsed with parse_hand_file: {len(hands)} hands")
    except Exception as e:
        print("parse_hand_file failed on coin file:", e)
else:
    print("coin file does not exist")
