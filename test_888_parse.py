from pathlib import Path
from poker_888_importer import parse_888poker_file

sample_dir = Path(r"C:\misc\888poker_hand_history\Sharkendahl")
files = list(sample_dir.glob("*.txt"))[:3]
for f in files:
    hands = parse_888poker_file(f)
    print(f"File: {f.name} -> Parsed {len(hands)} hands")
    for h in hands[:2]:
        print(f"  Hand ID: {h.hand_id}, Players: {len(h.players)}, Actions: {len(h.actions)}, Site: {h.poker_site}")
