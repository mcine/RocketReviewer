import sys
sys.path.insert(0, r"C:\misc\code\rangegame")
from hand_replayer import HandReplayer, parse_hand_file
from pathlib import Path

hands = parse_hand_file(Path(r"C:\misc\code\rangegame\data\nltest\HD2912939580.txt"))
replayer = HandReplayer()
replayer.load_hands(hands)
st = replayer.get_state()
print("State keys:", list(st.keys()))
for k, v in st.items():
    print(f"  {k}: {v}")
