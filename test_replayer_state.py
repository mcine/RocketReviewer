import sys
sys.path.insert(0, r"C:\misc\code\rangegame")

from hand_replayer import HandReplayer, parse_hand_file
from pathlib import Path

hands = parse_hand_file(Path(r"C:\misc\code\rangegame\data\nltest\HD2912939580.txt"))
replayer = HandReplayer()
replayer.load_hands(hands)

hand = replayer.current_hand()
print("Hand ID:", hand.hand_id)
print("Display steps count:", len(hand.display_steps))
print("Labels:", hand.display_step_labels)

for i in range(min(5, len(hand.display_steps))):
    replayer.display_index = i
    st = replayer.get_state()
    print(f"Step {i} ({hand.display_step_labels[i]}): street={st.get('street')}, pot={st.get('pot')}, board={st.get('board')}")
