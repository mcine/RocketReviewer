"""
888poker Hand History Parser.
Parses 888poker tournaments/cash games into the standard PokerHand format.
"""
import re
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_DIR = str(Path(__file__).resolve().parent)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

RANGEGAME_DIR = r"C:\misc\code\rangegame"
if RANGEGAME_DIR not in sys.path:
    sys.path.append(RANGEGAME_DIR)

from hand_replayer import PokerHand, PokerPlayer, Action

def _parse_card_tokens(text: str) -> List[str]:
    """Extract standard cards from text like '[ 9d, 2c ]' or '[ 2d, 2h, Ks ]'."""
    cards = re.findall(r'[2-9TJQKAtjqka][shdcSHDC]', text)
    return [c[0].upper() + c[1].lower() for c in cards]

def _parse_int_cents(val_str: str) -> int:
    """Parse amounts like '[20]', '40', '$0.50' into integer cents."""
    clean = re.sub(r'[^\d.]', '', val_str)
    if not clean:
        return 0
    val = float(clean)
    # If amount is formatted with decimals like 0.50, convert to cents
    if "." in clean:
        return round(val * 100)
    # If tournament chips or integer, represent as cents
    return round(val * 100)

def parse_888poker_hand(block: str) -> Optional[PokerHand]:
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines:
        return None

    m_id = re.search(r'Game (?:No\s*:?\s*|#)?(\d+)', block)
    hand_id = f"888_{m_id.group(1)}" if m_id else "888_Hand"

    m_btn = re.search(r'Seat #?(\d+) is the button', block)
    button_seat = int(m_btn.group(1)) if m_btn else 1

    variant = "No-Limit Hold'em"
    if "Omaha" in block:
        variant = "Pot-Limit Omaha"

    players: List[PokerPlayer] = []
    name_to_seat = {}

    # Seats
    for line in lines:
        m_seat = re.match(r'Seat (\d+):\s*(.+?)\s*\(\s*([\d.$]+)\s*\)', line)
        if m_seat:
            seat_num = int(m_seat.group(1))
            pname = m_seat.group(2).strip()
            stack = _parse_int_cents(m_seat.group(3))
            name_to_seat[pname] = seat_num
            players.append(PokerPlayer(seat=seat_num, name=pname, stack=stack))

    if not players:
        return None

    actions: List[Action] = []
    section = "preflop"

    for line in lines:
        # Sections
        if "** Dealing down cards **" in line:
            section = "hole_cards"
            continue
        if "** Dealing flop **" in line:
            section = "flop"
            cards = _parse_card_tokens(line)[:3]
            actions.append(Action("deal_flop", cards=cards))
            continue
        if "** Dealing turn **" in line:
            section = "turn"
            cards = _parse_card_tokens(line)[:1]
            actions.append(Action("deal_turn", cards=cards))
            continue
        if "** Dealing river **" in line:
            section = "river"
            cards = _parse_card_tokens(line)[:1]
            actions.append(Action("deal_river", cards=cards))
            continue
        if "** Summary **" in line:
            section = "summary"
            continue

        # Dealing hole cards to Hero
        m_dealt = re.match(r'Dealt to (.+?)\s*\[(.*?)\]', line)
        if m_dealt:
            pname = m_dealt.group(1).strip()
            seat = name_to_seat.get(pname)
            if seat:
                cards = _parse_card_tokens(m_dealt.group(2))
                actions.append(Action("deal_hole", seat=seat, cards=cards))
            continue

        # Blind posts & antes
        m_ante = re.match(r'(.+?)\s+posts ante\s*\[?([\d.$]+)\]?', line)
        if m_ante and m_ante.group(1) in name_to_seat:
            # antes can be added as post_sb or ignored in standard post
            continue

        m_sb = re.match(r'(.+?)\s+posts small blind\s*\[?([\d.$]+)\]?', line)
        if m_sb and m_sb.group(1) in name_to_seat:
            seat = name_to_seat[m_sb.group(1)]
            amt = _parse_int_cents(m_sb.group(2))
            actions.append(Action("post_sb", seat=seat, amount=amt))
            continue

        m_bb = re.match(r'(.+?)\s+posts big blind\s*\[?([\d.$]+)\]?', line)
        if m_bb and m_bb.group(1) in name_to_seat:
            seat = name_to_seat[m_bb.group(1)]
            amt = _parse_int_cents(m_bb.group(2))
            actions.append(Action("post_bb", seat=seat, amount=amt))
            continue

        # Actions
        m_fold = re.match(r'(.+?)\s+(folds|checks)', line)
        if m_fold and m_fold.group(1) in name_to_seat:
            seat = name_to_seat[m_fold.group(1)]
            act_type = "fold" if m_fold.group(2) == "folds" else "check"
            actions.append(Action(act_type, seat=seat))
            continue

        m_call = re.match(r'(.+?)\s+calls\s*\[?([\d.$]+)\]?', line)
        if m_call and m_call.group(1) in name_to_seat:
            seat = name_to_seat[m_call.group(1)]
            amt = _parse_int_cents(m_call.group(2))
            actions.append(Action("call", seat=seat, amount=amt))
            continue

        m_bet = re.match(r'(.+?)\s+bets\s*\[?([\d.$]+)\]?', line)
        if m_bet and m_bet.group(1) in name_to_seat:
            seat = name_to_seat[m_bet.group(1)]
            amt = _parse_int_cents(m_bet.group(2))
            actions.append(Action("bet", seat=seat, amount=amt))
            continue

        m_raise = re.match(r'(.+?)\s+raises\s*\[?([\d.$]+)\]?', line)
        if m_raise and m_raise.group(1) in name_to_seat:
            seat = name_to_seat[m_raise.group(1)]
            amt = _parse_int_cents(m_raise.group(2))
            actions.append(Action("raise", seat=seat, amount=amt))
            continue

        # Collected / win pot
        m_win = re.search(r'(.+?)\s+collected\s*\[?\s*([\d.$]+)\s*\]?', line)
        if m_win:
            winner_name = re.sub(r'^(?:First|Second)\s+runout\s+', '', m_win.group(1).strip())
            if winner_name in name_to_seat:
                seat = name_to_seat[winner_name]
                amt = _parse_int_cents(m_win.group(2))
                actions.append(Action("win_pot", seat=seat, amount=amt))
                continue

        # Showdown cards
        m_shows = re.match(r'(.+?)\s+shows\s*\[(.*?)\]', line)
        if m_shows and m_shows.group(1) in name_to_seat:
            seat = name_to_seat[m_shows.group(1)]
            cards = _parse_card_tokens(m_shows.group(2))
            actions.append(Action("deal_hole", seat=seat, cards=cards))
            continue

    # Extract metadata
    m_date = re.search(r'\*\*\*\s*(\d{2}\s+\d{2}\s+\d{4}\s+[\d:]+)', block)
    hand_date = m_date.group(1) if m_date else ""

    m_stakes = re.search(r'([\d.]+)/([\d.]+)\s+Blinds', block)
    stakes = f"{m_stakes.group(1)} / {m_stakes.group(2)}" if m_stakes else ""

    m_tbl = re.search(r'Table\s+(#[^(\n]+(?:\([^)]+\))?)', block)
    table_name = m_tbl.group(1).strip() if m_tbl else ""
    if not table_name:
        m_tourn = re.search(r'Tournament\s+#(\d+)', block)
        if m_tourn:
            table_name = f"Tournament #{m_tourn.group(1)}"

    hand = PokerHand(
        hand_id=hand_id,
        players=players,
        button_seat=button_seat,
        actions=actions,
        variant=variant,
        poker_site="888poker"
    )
    hand.hand_date = hand_date
    hand.stakes = stakes
    hand.table_name = table_name
    hand.game_type = "Tournament (BLAST)" if "Tournament" in block or "BLAST" in block else "Cash Game"
    return hand

def parse_888poker_file(filepath: Path) -> List[PokerHand]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    # Split by #Game No or ***** 888poker
    blocks = re.split(r'(?=#Game No|\*{5} 888poker)', text)
    hands = []
    for b in blocks:
        if b.strip():
            h = parse_888poker_hand(b.strip())
            if h:
                hands.append(h)
    return hands
