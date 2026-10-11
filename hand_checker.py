"""
Hand review and RocketSolver verification engine.
Reuses generic_hand_format and hand_replayer from C:\\misc\\code\\rangegame.
"""
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_DIR = str(Path(__file__).resolve().parent)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

RANGEGAME_DIR = r"C:\misc\code\rangegame"
if RANGEGAME_DIR not in sys.path:
    sys.path.append(RANGEGAME_DIR)

from generic_hand_format import serialize_poker_hand, parse_generic_hand_text, _fmt_cents
from hand_replayer import parse_hand_file, PokerHand, Action, PokerPlayer
from solver_bridge import RocketSolverBridge

# Position mapping for 6-max tables based on seat offset from button
POS_MAP_6MAX = {
    0: "BU",
    1: "SB",
    2: "BB",
    3: "EP", # UTG
    4: "MP", # HJ
    5: "CO", # Cutoff
}

def get_player_position(hand: PokerHand, seat: int) -> str:
    """Calculate standard position name (BU, SB, BB, EP, MP, CO)."""
    seats = sorted(hand.players.keys())
    if hand.button_seat not in seats:
        return f"Seat {seat}"
    btn_idx = seats.index(hand.button_seat)
    seat_idx = seats.index(seat)
    offset = (seat_idx - btn_idx) % len(seats)
    if len(seats) == 6:
        return POS_MAP_6MAX.get(offset, f"Pos-{offset}")
    elif len(seats) == 2:
        return "BU/SB" if offset == 0 else "BB"
    elif offset == 0:
        return "BU"
    elif offset == 1:
        return "SB"
    elif offset == 2:
        return "BB"
    elif offset == 3:
        return "EP"
    elif offset == len(seats) - 1:
        return "CO"
    else:
        return f"MP{offset-3}"

def parse_coin_poker_text(text: str) -> List[PokerHand]:
    """Converter for CoinPoker hand histories into PokerHand format."""
    # Normalize USDT character ₮ and crypto symbols to $
    normalized = text.replace("₮", "$").replace("USDT", "$")
    blocks = re.split(r'(?=^CoinPoker Hand )', normalized, flags=re.M)
    hands: List[PokerHand] = []

    for block in blocks:
        if not block.strip():
            continue
        # Convert header to generic compatible
        m_id = re.search(r'CoinPoker Hand #?(\d+)', block)
        hand_id = m_id.group(1) if m_id else "CP_Hand"
        
        m_btn = re.search(r'Seat #(\d+) is the button', block)
        button_seat = int(m_btn.group(1)) if m_btn else 1

        players = []
        for line in block.splitlines():
            pm = re.match(r'Seat (\d+):\s*(.+?)\s*\(\$?([\d.]+)\s+in chips\)', line)
            if pm:
                s = int(pm.group(1))
                name = pm.group(2).strip()
                stack = round(float(pm.group(3)) * 100)
                players.append(PokerPlayer(seat=s, name=name, stack=stack))

        if not players:
            continue

        # Extract actions
        actions = []
        section = "preflop"
        name_to_seat = {p.name: p.seat for p in players}

        for line in block.splitlines():
            line = line.strip()
            if '*** HOLE CARDS ***' in line:
                section = "hole_cards"
                continue
            if '*** FLOP ***' in line:
                cards = re.findall(r'[2-9TJQKAtjqka][shdcSHDC]', line)[:3]
                actions.append(Action("deal_flop", cards=cards))
                section = "flop"
                continue
            if '*** TURN ***' in line:
                cards = re.findall(r'\[([^\]]+)\]', line)
                turn = re.findall(r'[2-9TJQKAtjqka][shdcSHDC]', cards[-1]) if cards else []
                actions.append(Action("deal_turn", cards=turn[:1]))
                section = "turn"
                continue
            if '*** RIVER ***' in line:
                cards = re.findall(r'\[([^\]]+)\]', line)
                river = re.findall(r'[2-9TJQKAtjqka][shdcSHDC]', cards[-1]) if cards else []
                actions.append(Action("deal_river", cards=river[:1]))
                section = "river"
                continue
            if '*** SHOWDOWN ***' in line or '*** SUMMARY ***' in line:
                section = "end"
                continue

            # Blinds
            m_sb = re.match(r'(.+?):\s*posts small blind \$?([\d.]+)', line)
            if m_sb and m_sb.group(1).strip() in name_to_seat:
                actions.append(Action("post_sb", seat=name_to_seat[m_sb.group(1).strip()], amount=round(float(m_sb.group(2))*100)))
                continue
            m_bb = re.match(r'(.+?):\s*posts big blind \$?([\d.]+)', line)
            if m_bb and m_bb.group(1).strip() in name_to_seat:
                actions.append(Action("post_bb", seat=name_to_seat[m_bb.group(1).strip()], amount=round(float(m_bb.group(2))*100)))
                continue

            # Hole cards
            if section == "hole_cards":
                m_deal = re.match(r'Dealt to (.+?)\s*\[(.*?)\]', line)
                if m_deal and m_deal.group(1).strip() in name_to_seat:
                    cards = m_deal.group(2).split()
                    actions.append(Action("deal_hole", seat=name_to_seat[m_deal.group(1).strip()], cards=cards))
                    continue

            # Actions
            m_act = re.match(r'(.+?):\s*(folds|checks)', line)
            if m_act and m_act.group(1).strip() in name_to_seat:
                act_type = "fold" if m_act.group(2) == "folds" else "check"
                actions.append(Action(act_type, seat=name_to_seat[m_act.group(1).strip()]))
                continue

            m_call = re.match(r'(.+?):\s*calls \$?([\d.]+)', line)
            if m_call and m_call.group(1).strip() in name_to_seat:
                actions.append(Action("call", seat=name_to_seat[m_call.group(1).strip()], amount=round(float(m_call.group(2))*100)))
                continue

            m_bet = re.match(r'(.+?):\s*bets \$?([\d.]+)', line)
            if m_bet and m_bet.group(1).strip() in name_to_seat:
                actions.append(Action("bet", seat=name_to_seat[m_bet.group(1).strip()], amount=round(float(m_bet.group(2))*100)))
                continue

            m_raise = re.match(r'(.+?):\s*raises \$?[\d.]+ to \$?([\d.]+)', line)
            if m_raise and m_raise.group(1).strip() in name_to_seat:
                actions.append(Action("raise", seat=name_to_seat[m_raise.group(1).strip()], amount=round(float(m_raise.group(2))*100)))
                continue

            # Win pot
            if section == "end":
                m_win = re.match(r'(.+?)\s+collected \$?([\d.]+)', line)
                if m_win and m_win.group(1).strip() in name_to_seat:
                    actions.append(Action("win_pot", seat=name_to_seat[m_win.group(1).strip()], amount=round(float(m_win.group(2))*100)))
                    continue

        hand = PokerHand(hand_id=hand_id, players=players, button_seat=button_seat, actions=actions, variant="No-Limit Hold'em", poker_site="CoinPoker")
        hands.append(hand)

    return hands

def load_all_test_hands(dir_path: str = r"C:\misc\code\rangegame\data\nltest") -> List[PokerHand]:
    """Loads all hands from test directory."""
    path = Path(dir_path)
    all_hands = []
    for f in sorted(path.glob("*.txt")):
        try:
            hands = parse_hand_file(f)
            if not hands:
                # Try CoinPoker parser fallback
                text = f.read_text(encoding="utf-8", errors="replace")
                hands = parse_coin_poker_text(text)
            all_hands.extend(hands)
        except Exception as e:
            print(f"Error loading {f.name}: {e}")
    return all_hands

def get_hero_info(hand: PokerHand):
    """Find Hero's seat, position, and hole cards."""
    hero_seat = None
    hero_cards = []

    # Check for player named Hero
    for seat, player in hand.players.items():
        if player.name.lower() == "hero":
            hero_seat = seat
            break

    # Look for deal_hole actions with cards
    for act in hand.actions:
        if act.action_type in ("deal_hole", "holecards") and act.cards:
            if hero_seat is None or act.seat == hero_seat:
                hero_seat = act.seat
                hero_cards = act.cards
                break

    pos = get_player_position(hand, hero_seat) if hero_seat else "Unknown"
    return hero_seat, pos, hero_cards

# Standard Card and Hand utilities
RANKS_STR = "23456789TJQKA"
RANK_VAL = {r: i for i, r in enumerate(RANKS_STR)}

def to_canonical_hand(cards: List[str]) -> str:
    """Converts 2 card strings like ['Qd', 'Jh'] into canonical format 'QJo'."""
    if not cards or len(cards) < 2:
        return ""
    c1, c2 = cards[0], cards[1]
    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()
    if RANK_VAL.get(r1, 0) < RANK_VAL.get(r2, 0):
        r1, r2, s1, s2 = r2, r1, s2, s1
    if r1 == r2:
        return f"{r1}{r2}"
    elif s1 == s2:
        return f"{r1}{r2}s"
    else:
        return f"{r1}{r2}o"

# Exact RocketSolver 6-max 100bb Opening Ranges
ROCKET_6MAX_OPEN = {
    "EP": {
        "pure": {
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s",
            "KQs", "KJs", "KTs",
            "QJs", "QTs",
            "JTs",
            "T9s", "98s", "87s", "76s",
            "AKo", "AQo", "KQo"
        },
        "mixed": {"55", "A2s", "AJo", "KJo", "ATo"}
    },
    "MP": {
        "pure": {
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s",
            "QJs", "QTs", "Q9s",
            "JTs", "J9s",
            "T9s", "T8s",
            "98s", "87s", "76s", "65s",
            "AKo", "AQo", "AJo", "KQo", "KJo"
        },
        "mixed": {"44", "ATo", "KTo"}
    },
    "CO": {
        "pure": {
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
            "QJs", "QTs", "Q9s", "Q8s",
            "JTs", "J9s", "J8s",
            "T9s", "T8s",
            "98s", "97s",
            "87s", "76s", "65s", "54s",
            "AKo", "AQo", "AJo", "ATo", "KQo", "KJo", "QJo", "JTo"
        },
        "mixed": {"KTo", "QTo", "A9o", "A8o"}
    },
    "BU": {
        "pure": {
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
            "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s",
            "JTs", "J9s", "J8s", "J7s", "J6s", "J5s", "J4s",
            "T9s", "T8s", "T7s", "T6s",
            "98s", "97s", "96s", "87s", "86s", "85s", "76s", "75s", "65s", "64s", "54s", "53s", "43s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
            "KQo", "KJo", "KTo", "K9o", "K8o", "K7o",
            "QJo", "QTo", "Q9o", "Q8o",
            "JTo", "J9o", "J8o",
            "T9o", "T8o",
            "98o", "87o"
        },
        "mixed": {"K6o", "K5o", "Q7o", "J7o", "T7o", "97o", "76o", "65o"}
    },
    "SB": {
        "pure": {
            "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
            "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s",
            "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s",
            "JTs", "J9s", "J8s", "J7s", "J6s",
            "T9s", "T8s", "T7s",
            "98s", "97s", "87s", "86s", "76s", "65s", "54s",
            "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o",
            "KQo", "KJo", "KTo", "K9o",
            "QJo", "QTo", "Q9o",
            "JTo", "J9o",
            "T9o", "98o"
        },
        "mixed": {"A6o", "A5o", "A4o", "A3o", "A2o", "K8o", "Q8o", "J8o", "87o"}
    }
}

def evaluate_hand_made_strength(hole: List[str], board: List[str]):
    """Returns (category, description) of Hero's hand strength on the current board."""
    if not hole:
        return ("none", "No hole cards")
    if not board:
        h_ranks = [c[0].upper() for c in hole]
        if h_ranks[0] == h_ranks[1]:
            return ("pocket_pair", f"Pocket {h_ranks[0]}s")
        return ("high_card", f"{max(h_ranks, key=lambda r: RANK_VAL.get(r, 0))}-high")

    from collections import Counter
    h_ranks = [c[0].upper() for c in hole]
    b_ranks = [c[0].upper() for c in board]
    h_suits = [c[1].lower() for c in hole]
    b_suits = [c[1].lower() for c in board]

    all_ranks = h_ranks + b_ranks
    all_suits = h_suits + b_suits

    # Check flush
    suit_counts = Counter(all_suits)
    flush_suit = next((s for s, cnt in suit_counts.items() if cnt >= 5), None)

    # Check straight
    def get_straight_high(ranks):
        vals = set(RANK_VAL[r] for r in ranks if r in RANK_VAL)
        if 12 in vals: # Ace low
            vals.add(-1)
        for high in range(12, 2, -1):
            if all(high - i in vals for i in range(5)):
                return high
        return -1

    straight_high = get_straight_high(all_ranks)

    # Straight flush
    if flush_suit:
        flush_ranks = [c[0].upper() for c in hole + board if c[1].lower() == flush_suit]
        sf_high = get_straight_high(flush_ranks)
        if sf_high != -1:
            return ("monster", f"Straight Flush ({RANKS_STR[sf_high]}-high)")

    rank_counts = Counter(all_ranks)
    counts_sorted = sorted(rank_counts.items(), key=lambda x: (x[1], RANK_VAL.get(x[0], 0)), reverse=True)

    if counts_sorted[0][1] >= 4:
        return ("monster", f"Four of a Kind ({counts_sorted[0][0]}s)")
    if counts_sorted[0][1] == 3 and counts_sorted[1][1] >= 2:
        return ("monster", f"Full House ({counts_sorted[0][0]}s full of {counts_sorted[1][0]}s)")
    if flush_suit:
        return ("flush", f"Flush ({flush_suit.upper()})")
    if straight_high != -1:
        return ("straight", f"Straight ({RANKS_STR[straight_high]}-high)")
    if counts_sorted[0][1] == 3:
        trips_rank = counts_sorted[0][0]
        if h_ranks.count(trips_rank) == 2:
            return ("set", f"Set of {trips_rank}s")
        elif h_ranks.count(trips_rank) == 1:
            return ("trips", f"Three of a Kind ({trips_rank}s)")
        else:
            return ("board_trips", f"Board Trips ({trips_rank}s)")

    # Two pair
    if counts_sorted[0][1] == 2 and counts_sorted[1][1] == 2:
        p1, p2 = counts_sorted[0][0], counts_sorted[1][0]
        h_has_p1 = p1 in h_ranks
        h_has_p2 = p2 in h_ranks
        if h_has_p1 and h_has_p2:
            return ("two_pair", f"Two Pair ({p1}s and {p2}s)")
        elif (h_ranks[0] == h_ranks[1]) and (p1 in h_ranks or p2 in h_ranks):
            return ("two_pair", f"Two Pair ({p1}s and {p2}s)")
        elif h_has_p1 or h_has_p2:
            hit = p1 if h_has_p1 else p2
            board_p = p2 if h_has_p1 else p1
            return ("two_pair_board", f"Two Pair ({hit}s with board {board_p}s)")
        else:
            return ("board_two_pair", f"Board Two Pair ({p1}s and {p2}s)")

    # One pair
    if counts_sorted[0][1] == 2:
        pair_rank = counts_sorted[0][0]
        if h_ranks[0] == h_ranks[1]:
            max_b = max(RANK_VAL.get(r, 0) for r in b_ranks)
            p_val = RANK_VAL.get(pair_rank, 0)
            if p_val > max_b:
                return ("overpair", f"Overpair ({pair_rank}s)")
            else:
                return ("pocket_pair", f"Pocket Pair ({pair_rank}s)")
        elif pair_rank in h_ranks:
            max_b = max(RANK_VAL.get(r, 0) for r in b_ranks)
            min_b = min(RANK_VAL.get(r, 0) for r in b_ranks)
            p_val = RANK_VAL.get(pair_rank, 0)
            if p_val == max_b:
                kicker = h_ranks[1] if h_ranks[0] == pair_rank else h_ranks[0]
                return ("top_pair", f"Top Pair ({pair_rank}s, {kicker} kicker)")
            elif p_val == min_b:
                return ("bottom_pair", f"Bottom Pair ({pair_rank}s)")
            else:
                return ("second_pair", f"Second Pair ({pair_rank}s)")
        else:
            return ("board_pair", f"Board Pair ({pair_rank}s)")

    high_c = max(h_ranks, key=lambda r: RANK_VAL.get(r, 0))
    return ("high_card", f"{high_c}-high")

def verify_hand_with_solver(hand: PokerHand, bridge: Optional[RocketSolverBridge] = None, cancel_check=None) -> Dict[str, Any]:
    """
    Simulates and verifies a hand against RocketSolver 6-max GTO strategy.
    Accurately checks preflop opens/folds by position and board-aware postflop defense.
    Resets solver strategy view back to root after the hand.
    """
    hero_seat, hero_pos, hero_cards = get_hero_info(hand)
    review_reasons = []
    marked_for_review = False
    street_analyses = []

    card_str = "".join(hero_cards) if hero_cards else ""
    canon_hand = to_canonical_hand(hero_cards)

    board = []
    for act in hand.actions:
        if act.action_type in ("deal_flop", "deal_turn", "deal_river"):
            board.extend(act.cards)

    if cancel_check and cancel_check():
        return {
            "hand_id": hand.hand_id,
            "cancelled": True,
            "variant": hand.variant or "No-Limit Hold'em",
            "poker_site": getattr(hand, "poker_site", "Unknown"),
            "hero_seat": hero_seat,
            "hero_pos": hero_pos,
            "hero_cards": hero_cards,
            "board": board,
            "marked_for_review": False,
            "review_reasons": [],
            "street_analyses": []
        }

    # 0. If live RocketSolver bridge is available, step action-by-action directly inside the solver UI
    if bridge and bridge.ensure_ready():
        try:
            step_res = bridge.step_hand(hand, cancel_check=cancel_check)
            if step_res.get("cancelled"):
                return {
                    "hand_id": hand.hand_id,
                    "cancelled": True,
                    "variant": hand.variant or "No-Limit Hold'em",
                    "poker_site": getattr(hand, "poker_site", "Unknown"),
                    "hero_seat": hero_seat,
                    "hero_pos": hero_pos,
                    "hero_cards": hero_cards,
                    "board": board,
                    "marked_for_review": False,
                    "review_reasons": [],
                    "street_analyses": []
                }
            if not step_res.get("error"):
                return {
                    "hand_id": hand.hand_id,
                    "variant": hand.variant or "No-Limit Hold'em",
                    "poker_site": getattr(hand, "poker_site", "Unknown"),
                    "hero_seat": hero_seat,
                    "hero_pos": hero_pos,
                    "hero_cards": hero_cards,
                    "board": board,
                    "marked_for_review": step_res.get("marked_for_review", False),
                    "review_reasons": step_res.get("review_reasons", []),
                    "street_analyses": step_res.get("street_analyses", [])
                }
        except Exception as e:
            if cancel_check and cancel_check():
                return {
                    "hand_id": hand.hand_id,
                    "cancelled": True,
                    "variant": hand.variant or "No-Limit Hold'em",
                    "poker_site": getattr(hand, "poker_site", "Unknown"),
                    "hero_seat": hero_seat,
                    "hero_pos": hero_pos,
                    "hero_cards": hero_cards,
                    "board": board,
                    "marked_for_review": False,
                    "review_reasons": [],
                    "street_analyses": []
                }
            print(f"Live solver stepping fallback to rule-based: {e}")

    street = "Preflop"
    street_actions = {"Preflop": [], "Flop": [], "Turn": [], "River": []}

    for act in hand.actions:
        if act.action_type == "deal_flop":
            street = "Flop"
            board.extend(act.cards)
            continue
        elif act.action_type == "deal_turn":
            street = "Turn"
            board.extend(act.cards)
            continue
        elif act.action_type == "deal_river":
            street = "River"
            board.extend(act.cards)
            continue
        elif act.action_type in ("fold", "check", "call", "bet", "raise"):
            street_actions[street].append(act)

    # 1. Analyze Preflop actions
    preflop_acts = street_actions["Preflop"]
    # Check if pot was unopened before Hero
    unopened_before_hero = True
    open_bettor = None

    for act in preflop_acts:
        if act.seat == hero_seat:
            break
        if act.action_type in ("bet", "raise"):
            unopened_before_hero = False
            open_bettor = act.seat
        elif act.action_type == "call":
            unopened_before_hero = False

    pos_key = hero_pos.upper() if hero_pos else "EP"
    if pos_key not in ROCKET_6MAX_OPEN:
        pos_key = "EP" if pos_key in ("UTG", "LJ") else ("MP" if pos_key == "HJ" else ("CO" if pos_key == "CO" else "BU"))

    pos_ranges = ROCKET_6MAX_OPEN.get(pos_key, ROCKET_6MAX_OPEN["EP"])
    pure_opens = pos_ranges["pure"]
    mixed_opens = pos_ranges["mixed"]

    hero_had_to_fold_preflop = False
    for act in preflop_acts:
        if act.seat == hero_seat and canon_hand:
            # Case A: Hero open-raises
            if unopened_before_hero and act.action_type == "raise":
                if canon_hand not in pure_opens and canon_hand not in mixed_opens:
                    marked_for_review = True
                    hero_had_to_fold_preflop = True
                    exp = (
                        f"Preflop: Hero raised {canon_hand} from {hero_pos}. "
                        f"In RocketSolver 6-max GTO strategy, {canon_hand} is a 100% Fold (0% Raise frequency). "
                        f"{hero_pos} opening range is ~13-15% (66+, A2s+, KTs+, QTs+, JTs, T9s-76s, AKo, AQo, KQo, mixed AJo/KJo). "
                        f"Hand has to be folded; check ended here."
                    )
                    review_reasons.append({
                        "street": "Preflop",
                        "action": "Raise",
                        "cards": card_str,
                        "position": hero_pos,
                        "explanation": exp
                    })

            # Case B: Hero open-folds a 100% pure open hand
            elif unopened_before_hero and act.action_type == "fold":
                if canon_hand in pure_opens:
                    marked_for_review = True
                    exp = (
                        f"Preflop: Hero folded {canon_hand} from {hero_pos}. "
                        f"In RocketSolver 6-max GTO strategy, {canon_hand} is a 100% Open/Raise. "
                        f"Fold is not an option in solver range (0% frequency)."
                    )
                    review_reasons.append({
                        "street": "Preflop",
                        "action": "Fold",
                        "cards": card_str,
                        "position": hero_pos,
                        "explanation": exp
                    })

            # Case C: Hero open-limps (except SB where limp is sometimes mixed)
            elif unopened_before_hero and act.action_type == "call" and hero_pos != "SB":
                marked_for_review = True
                hero_had_to_fold_preflop = True
                exp = (
                    f"Preflop: Hero open-limped with {canon_hand} from {hero_pos}. "
                    f"In 6-max GTO strategy, open-limping is -EV. Play raise-or-fold."
                )
                review_reasons.append({
                    "street": "Preflop",
                    "action": "Call",
                    "cards": card_str,
                    "position": hero_pos,
                    "explanation": exp
                })
            break

    # 2. Analyze Postflop streets (only if hand did not have to be folded preflop and Hero did not fold)
    hero_folded_preflop = any(a.seat == hero_seat and a.action_type == "fold" for a in preflop_acts)
    if not hero_had_to_fold_preflop and not hero_folded_preflop:
        current_board = []
        hand_ended_postflop = False
        for st_name in ["Flop", "Turn", "River"]:
            if hand_ended_postflop:
                break
            acts = street_actions[st_name]
            if st_name == "Flop":
                current_board = board[:3]
            elif st_name == "Turn":
                current_board = board[:4]
            elif st_name == "River":
                current_board = board[:5]

            for act in acts:
                if act.seat == hero_seat and hero_cards:
                    cat, desc = evaluate_hand_made_strength(hero_cards, current_board)

                    # Hero FOLD postflop check
                    if act.action_type == "fold":
                        hand_ended_postflop = True
                        # River: folding High Card, board pair (unimproved), bottom pair is 100% CORRECT!
                        if st_name == "River":
                            # Only flag if hero folded a monster or very strong made hand
                            if cat in ("monster", "flush", "straight", "set", "two_pair"):
                                marked_for_review = True
                                exp = (
                                    f"River: Hero folded {desc} with {card_str}. "
                                    f"In RocketSolver GTO strategy, folding strong made hands like {desc} "
                                    f"to standard bet sizing is overly exploitable."
                                )
                                review_reasons.append({
                                    "street": "River",
                                    "action": "Fold",
                                    "cards": card_str,
                                    "position": hero_pos,
                                    "explanation": exp
                                })
                        elif st_name == "Turn":
                            if cat in ("monster", "flush", "straight", "set", "two_pair"):
                                marked_for_review = True
                                exp = (
                                    f"Turn: Hero folded {desc} with {card_str}. "
                                    f"Solver strategy recommends continuing with {desc}."
                                )
                                review_reasons.append({
                                    "street": "Turn",
                                    "action": "Fold",
                                    "cards": card_str,
                                    "position": hero_pos,
                                    "explanation": exp
                                })
                        elif st_name == "Flop":
                            # On Flop, folding top pair+ with good kicker or overpair/set is a mistake
                            if cat in ("monster", "set", "two_pair", "overpair", "top_pair"):
                                marked_for_review = True
                                exp = (
                                    f"Flop: Hero folded {desc} with {card_str} on board {' '.join(current_board)}. "
                                    f"Solver strategy recommends defending with {desc} vs c-bet."
                                )
                                review_reasons.append({
                                    "street": "Flop",
                                    "action": "Fold",
                                    "cards": card_str,
                                    "position": hero_pos,
                                    "explanation": exp
                                })

    # Build street analyses output
    for st_name, acts in street_actions.items():
        for act in acts:
            street_analyses.append({
                "street": st_name,
                "seat": act.seat,
                "action": act.action_type,
                "amount": _fmt_cents(act.amount) if act.amount else "0",
                "solver_match": not any(r["street"] == st_name for r in review_reasons)
            })


    return {
        "hand_id": hand.hand_id,
        "variant": hand.variant or "No-Limit Hold'em",
        "poker_site": getattr(hand, "poker_site", "Unknown"),
        "hero_seat": hero_seat,
        "hero_pos": hero_pos,
        "hero_cards": hero_cards,
        "board": board,
        "marked_for_review": marked_for_review,
        "review_reasons": review_reasons,
        "street_analyses": street_analyses
    }
