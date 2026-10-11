import sys
sys.path.insert(0, r"C:\misc\code\rangegame")
from hand_replayer import parse_hand_file
from pathlib import Path

for name in ["HD2912941235.txt", "HD2912941417.txt", "RC4587173361.txt"]:
    hands = parse_hand_file(Path(r"C:\misc\code\rangegame\data\nltest") / name)
    for h in hands:
        hero_actions = [a for a in h.actions if a.seat == 2 or (h.players.get(a.seat) and h.players[a.seat].name.lower() == 'hero')]
        hole = [a.cards for a in h.actions if a.action_type == 'deal_hole' and a.cards]
        print(f"Hand {h.hand_id}: Hero hole={hole}, Hero actions={[a.action_type for a in hero_actions]}")
