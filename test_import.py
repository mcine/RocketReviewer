import sys
from pathlib import Path

# Add rangegame to sys.path to reuse format and importers
sys.path.insert(0, r"C:\misc\code\rangegame")

from hand_replayer import parse_hand_file, HandReplayer

test_dir = Path(r"C:\misc\code\rangegame\data\nltest")
for f in test_dir.glob("*.txt"):
    hands = parse_hand_file(f)
    print(f"File {f.name}: {len(hands)} hands")
    for h in hands:
        print(f"  Hand ID: {h.hand_id}, Site: {h.poker_site}, Variant: {h.variant}, Players: {len(h.players)}, Actions: {len(h.actions)}")
