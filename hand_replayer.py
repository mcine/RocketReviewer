"""Texas Hold'em Poker Hand Replayer – core module.

Provides data classes and a navigator for stepping through
recorded poker hands action by action.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from generic_hand_format import parse_generic_hand_text


def _fmt(cents: int) -> str:
    """Format integer cents as a dollar string, e.g. 1365 -> '13.65'."""
    if cents == 0:
        return "0"
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    d, c = divmod(cents, 100)
    return f"{sign}{d}.{c:02d}" if c else f"{sign}{d}"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class PokerPlayer:
    """A player occupying one seat at the table."""
    seat: int          # 1-10
    name: str
    stack: int = 1000


@dataclass
class Action:
    """A single event in the hand timeline.

    action_type values
    ------------------
    'post_sb', 'post_bb'                   – blind posts
    'deal_hole'                            – hole cards dealt to a player
    'deal_flop', 'deal_turn', 'deal_river' – community card deals
    'fold', 'check', 'call', 'bet', 'raise'
    'win_pot'                              – player wins the pot
    """
    action_type: str
    seat: Optional[int] = None
    amount: int = 0
    cards: List[str] = field(default_factory=list)  # e.g. ['Ah', 'Kd']
    description: str = ""


# ── Display-step computation ───────────────────────────────────────────────────

def _compute_display_steps(actions: List[Action]) -> Tuple[List[int], List[str]]:
    """Group raw actions into meaningful display steps.

    Returns
    -------
    steps : list of raw-action counts.
        Replaying ``actions[:steps[i]]`` gives the table state at display step *i*.
    labels : matching step-type strings.
        'start' | 'preflop' | 'action' | 'flop' | 'turn' | 'river' | 'showdown'
    """
    # Count initial setup actions so they are applied automatically on first display.
    initial_setup = 0
    for act in actions:
        if act.action_type in ("post_sb", "post_bb", "deal_hole", "return_uncalled"):
            initial_setup += 1
        else:
            break

    steps: List[int] = [initial_setup]
    labels: List[str] = ["start"]

    for i, action in enumerate(actions):
        action_type = action.action_type

        # Skip creating display steps for pre-flop and deal_hole states.
        # The user should not need to press a button to step through these —
        # they are automatic transitions that happen before the first action.
        if action_type in ("post_sb", "post_bb", "deal_hole", "return_uncalled"):
            continue

        if action_type == "win_pot":
            # Group consecutive win_pot actions into one simultaneous showdown step.
            if i + 1 < len(actions) and actions[i + 1].action_type == "win_pot":
                continue
            step_label = "showdown"
        elif action_type == "deal_flop":
            step_label = "flop"
        elif action_type == "deal_turn":
            step_label = "turn"
        elif action_type == "deal_river":
            step_label = "river"
        else:
            step_label = "action"

        steps.append(i + 1)
        labels.append(step_label)

    return steps, labels


# ── Hand ───────────────────────────────────────────────────────────────────────

class PokerHand:
    """A complete poker hand: players, button, ordered action list."""

    def __init__(
        self,
        hand_id: str,
        players: List[PokerPlayer],
        button_seat: int,
        actions: Optional[List[Action]] = None,
        variant: str = "",
        poker_site: str = "",
        hand_date: str = "",
        table_name: str = "",
        stakes: str = "",
    ) -> None:
        self.hand_id = hand_id
        self.players: Dict[int, PokerPlayer] = {p.seat: p for p in players}
        self.button_seat = button_seat
        self.actions: List[Action] = actions or []
        self.variant: str = variant
        self.poker_site: str = poker_site
        self.hand_date: str = hand_date
        self.table_name: str = table_name
        self.stakes: str = stakes
        self.display_steps, self.display_step_labels = _compute_display_steps(self.actions)

    # ── Utility ────────────────────────────────────────────────────────────────

    def _seat_offset(self, offset: int) -> int:
        seats = sorted(self.players)
        if not seats:
            return 0
        if self.button_seat not in seats:
            return seats[offset % len(seats)]
        idx = seats.index(self.button_seat)
        return seats[(idx + offset) % len(seats)]

    def sb_seat(self) -> int:
        """Seat of the small blind (1 position clockwise from button, i.e. offset +1)."""
        return self._seat_offset(1)

    def bb_seat(self) -> int:
        """Seat of the big blind (2 positions clockwise from button, i.e. offset +2)."""
        return self._seat_offset(2)


# ── Replayer ───────────────────────────────────────────────────────────────────

class HandReplayer:
    """Navigate a collection of PokerHand objects step-by-step."""

    def __init__(self) -> None:
        self.num_players: int = 6
        self.hands: List[PokerHand] = []
        self.hand_index: int = 0
        self.display_index: int = 0

    def load_hands(self, hands: List[PokerHand]) -> None:
        self.hands = hands
        self.hand_index = 0
        self.display_index = 0
        # Initialize replayer indices without debug output

    def step_forward(self) -> None:
        hand = self.current_hand()
        if hand and self.display_index < len(hand.display_steps) - 1:
            self.display_index += 1


    def step_back(self) -> None:
        if self.display_index > 0:
            self.display_index -= 1
        # otherwise no-op

    def next_hand(self) -> None:
        if self.hand_index < len(self.hands) - 1:
            self.hand_index += 1
            self.display_index = 0

    def prev_hand(self) -> None:
        if self.hand_index > 0:
            self.hand_index -= 1
            self.display_index = 0

    def can_step_forward(self) -> bool:
        hand = self.current_hand()
        return bool(hand) and self.display_index < len(hand.display_steps) - 1

    def can_step_back(self) -> bool:
        return self.display_index > 0

    def can_next_hand(self) -> bool:
        return self.hand_index < len(self.hands) - 1

    def can_prev_hand(self) -> bool:
        return self.hand_index > 0

    def current_hand(self) -> Optional[PokerHand]:
        return self.hands[self.hand_index] if self.hands else None

    def get_state(self) -> dict:
        hand = self.current_hand()
        if not hand:
            return self._empty_state()

        raw_count  = hand.display_steps[self.display_index]
        step_label = hand.display_step_labels[self.display_index]

        stacks: Dict[int, int]  = {s: p.stack for s, p in hand.players.items()}
        active: Dict[int, bool] = {s: True    for s in hand.players}
        bets:   Dict[int, int]  = {s: 0       for s in hand.players}
        cards:  Dict[int, list] = {s: []      for s in hand.players}
        player_labels: Dict[int, str] = {s: "" for s in hand.players}
        board: List[str] = []
        winners: List[tuple] = []
        pot    = 0
        street = "preflop"

        for act in hand.actions[:raw_count]:
            t = act.action_type

            if t in ("post_sb", "post_bb", "call", "bet"):
                stacks[act.seat] -= act.amount
                bets[act.seat]   += act.amount
                pot              += act.amount
            elif t == "return_uncalled":
                stacks[act.seat] += act.amount
                bets[act.seat]   -= act.amount
                pot              -= act.amount
            elif t == "raise":
                additional = act.amount - bets[act.seat]
                stacks[act.seat] -= additional
                bets[act.seat]    = act.amount
                pot              += additional
            elif t == "fold":
                active[act.seat] = False
                # If only one active player remains, return any uncalled portion of bets
                if sum(1 for is_act in active.values() if is_act) <= 1:
                    for s, b in list(bets.items()):
                        other_max = max((bets[o] for o in bets if o != s), default=0)
                        if b > other_max:
                            uncalled = b - other_max
                            stacks[s] += uncalled
                            bets[s]   -= uncalled
                            pot       -= uncalled
            elif t == "deal_hole":
                if act.cards:
                    cards[act.seat] = act.cards
                elif not cards.get(act.seat):
                    cards[act.seat] = ["back", "back"]
            elif t == "deal_flop":
                board.extend(act.cards[:3])
                street = "flop"
                bets   = {s: 0 for s in bets}
                player_labels = {s: "" for s in hand.players}
            elif t == "deal_turn":
                board.extend(act.cards[:1])
                street = "turn"
                bets   = {s: 0 for s in bets}
                player_labels = {s: "" for s in hand.players}
            elif t == "deal_river":
                board.extend(act.cards[:1])
                street = "river"
                bets   = {s: 0 for s in bets}
                player_labels = {s: "" for s in hand.players}
            elif t == "win_pot":
                # Ensure any residual uncalled bet across all players is returned
                for s, b in list(bets.items()):
                    other_max = max((bets[o] for o in bets if o != s), default=0)
                    if b > other_max:
                        uncalled = b - other_max
                        stacks[s] += uncalled
                        bets[s]   -= uncalled
                        pot       -= uncalled
                stacks[act.seat] += act.amount
                pot              -= act.amount
                winners.append((act.seat, act.amount))
                bets = {s: 0 for s in hand.players}

            if act.seat and t == "fold":
                player_labels[act.seat] = "FOLD"
            elif act.seat and t == "check":
                player_labels[act.seat] = "CHECK"
            elif act.seat and t == "call":
                player_labels[act.seat] = f"CALL ${_fmt(act.amount)}"
            elif act.seat and t == "bet":
                player_labels[act.seat] = f"BET ${_fmt(act.amount)}"
            elif act.seat and t == "raise":
                player_labels[act.seat] = f"RAISE ${_fmt(act.amount)}"
            elif act.seat and t == "win_pot":
                player_labels[act.seat] = f"WON ${_fmt(act.amount)}"

        # After all win_pot actions are applied the pot should be 0;
        # any residual comes from uncalled bets that were returned but not
        # parsed, so clamp it here so the table never shows a phantom pot.
        if winners:
            pot = 0

        if step_label in ("flop", "turn", "river", "showdown"):
            display_street = step_label.upper()
        else:
            display_street = street.upper()

        return {
            "hand":           hand,
            "board":          board,
            "pot":            pot,
            "player_stacks":  stacks,
            "player_bets":    bets,
            "player_active":  active,
            "player_cards":   cards,
            "player_labels":  player_labels,
            "winners":        winners,
            "street":         street,
            "display_street": display_street,
            "step_label":     step_label,
            "display_index":  self.display_index,
            "total_steps":    len(hand.display_steps) - 1,
            "hand_index":     self.hand_index,
            "total_hands":    len(self.hands),
            "button_seat":    hand.button_seat,
            "sb_seat":        hand.sb_seat(),
            "bb_seat":        hand.bb_seat(),
            "variant":        getattr(hand, "variant", ""),
        }

    @staticmethod
    def _empty_state() -> dict:
        return {
            "hand": None, "board": [], "pot": 0,
            "player_stacks": {}, "player_bets": {}, "player_active": {},
            "player_cards": {}, "player_labels": {}, "winners": [],
            "street": "preflop", "display_street": "PREFLOP", "step_label": "start",
            "display_index": 0, "total_steps": 0,
            "hand_index": 0, "total_hands": 0,
            "button_seat": 1, "sb_seat": 2, "bb_seat": 3,
        }


# ── Hand file parser ───────────────────────────────────────────────────────────

def _cents(s: str) -> int:
    """Convert a dollar string like '0.23' or '$0.23' to integer cents."""
    return round(float(s.lstrip("$")) * 100)


def _parse_cards_str(s: str) -> List[str]:
    """Extract card codes from a string, e.g. '[Ts Ah]' -> ['Ts', 'Ah']."""
    return re.findall(r'[2-9TJQKAtjqka][shdcSHDC]', s)


def _parse_single_hand(text: str) -> Optional[PokerHand]:
    lines = text.splitlines()
    if not lines:
        return None

    # ── Header ──────────────────────────────────────────────────────────────
    m = re.match(r'Poker Hand #(\S+):', lines[0])
    hand_id = m.group(1) if m else "?"

    # Extract poker site from header line
    poker_site = "GG-Poker"
    header_line = lines[0]
    if "PokerStars" in header_line:
        poker_site = "PokerStars"
    elif "CoinPoker" in header_line or "CoinPoker" in text:
        poker_site = "CoinPoker"
    elif "888poker" in text or "#Game No" in header_line:
        poker_site = "888poker"
    elif "Poker Hand #" in header_line or "RushAndCash" in text or "Table '" in text:
        poker_site = "GG-Poker"

    hand_date = ""
    if " - " in header_line:
        parts = header_line.split(" - ")
        if len(parts) > 1:
            hand_date = parts[1].strip()

    # Attempt to detect poker variant from the header/text (e.g. No-Limit Hold'em)
    variant = ""
    txt = text.lower()
    if "pot-limit omaha" in txt or "pot limit omaha" in txt or "plo" in txt:
        variant = "Pot-Limit Omaha"
    elif "fixed-limit hold" in txt or "fixed limit" in txt:
        variant = "Fixed-Limit Hold'em"
    elif "no-limit" in txt or "no limit" in txt or "nl" in txt:
        variant = "No-Limit Hold'em"
    else:
        # fallback: look for "hold'em" or "holdem" or "omaha"
        if "hold'em" in txt or "holdem" in txt:
            variant = "No-Limit Hold'em"
        elif "omaha" in txt:
            variant = "Pot-Limit Omaha"

    if "RushAndCash" in text or hand_id.startswith("RC"):
        if "omaha" in variant.lower():
            variant = "Pot-Limit Omaha - Fast-Fold"
        else:
            variant = "No-Limit Hold'em - Fast-Fold"

    table_name = ""
    m_tbl = re.search(r"Table '([^']+)'", text)
    if m_tbl:
        table_name = m_tbl.group(1)

    stakes = ""
    m_stk = re.search(r'\(\$([\d.]+)/\$([\d.]+)\)', header_line)
    if m_stk:
        stakes = f"${m_stk.group(1)} / ${m_stk.group(2)}"

    m = re.search(r'Seat #(\d+) is the button', text)
    button_seat = int(m.group(1)) if m else 1

    # ── Seats ───────────────────────────────────────────────────────────────
    name_to_seat: Dict[str, int] = {}
    players: List[PokerPlayer] = []
    for line in lines:
        m = re.match(r'Seat (\d+): (\S+) \(\$?([\d.]+) in chips\)', line)
        if m:
            seat  = int(m.group(1))
            name  = m.group(2)
            stack = _cents(m.group(3))
            name_to_seat[name] = seat
            players.append(PokerPlayer(seat=seat, name=name, stack=stack))

    if not players:
        return None

    # ── Actions ─────────────────────────────────────────────────────────────
    actions: List[Action] = []
    section = "preflop"

    for line in lines:
        line = line.strip()

        # ── Section markers ──────────────────────────────────────────────
        if '* HOLE CARDS *' in line:
            section = "hole_cards"
            continue
        if re.search(r'\*+.*?\bFLOP\b.*?\*+', line, re.IGNORECASE):
            section = "flop"
            cards = _parse_cards_str(line)[:3]
            actions.append(Action("deal_flop", cards=cards))
            continue
        if re.search(r'\*+.*?\bTURN\b.*?\*+', line, re.IGNORECASE):
            section = "turn"
            brackets = re.findall(r'\[([^\]]+)\]', line)
            if brackets:
                cards = _parse_cards_str(brackets[-1])
                turn = cards[-1:] if len(brackets) == 1 and len(cards) > 1 else cards[:1]
            else:
                all_cards = _parse_cards_str(line)
                turn = all_cards[-1:] if all_cards else []
            actions.append(Action("deal_turn", cards=turn))
            continue
        if re.search(r'\*+.*?\bRIVER\b.*?\*+', line, re.IGNORECASE):
            section = "river"
            brackets = re.findall(r'\[([^\]]+)\]', line)
            if brackets:
                cards = _parse_cards_str(brackets[-1])
                river = cards[-1:] if len(brackets) == 1 and len(cards) > 1 else cards[:1]
            else:
                all_cards = _parse_cards_str(line)
                river = all_cards[-1:] if all_cards else []
            actions.append(Action("deal_river", cards=river))
            continue
        if re.search(r'\*+.*?\b(?:SHOWDOWN|SUMMARY)\b.*?\*+', line, re.IGNORECASE):
            section = "end"
            continue

        # ── Pot collections ──────────────────────────────────────────────
        m_coll = re.search(r'(\S+)\s+collected\s+\$?([\d.]+)\s+from\b', line)
        if m_coll and m_coll.group(1) in name_to_seat:
            seat = name_to_seat[m_coll.group(1)]
            actions.append(Action("win_pot", seat=seat, amount=_cents(m_coll.group(2))))
            continue

        # ── Uncalled bet returned ────────────────────────────────────────
        m_unc = re.search(r'Uncalled bet \(?\$?([\d.]+)\)? returned to (\S+)', line)
        if m_unc and m_unc.group(2) in name_to_seat:
            actions.append(Action("return_uncalled", seat=name_to_seat[m_unc.group(2)], amount=_cents(m_unc.group(1))))
            continue

        # ── Blind posts ──────────────────────────────────────────────────
        m = re.match(r'(\S+): posts small blind \$([\d.]+)', line)
        if m and m.group(1) in name_to_seat:
            actions.append(Action("post_sb", seat=name_to_seat[m.group(1)], amount=_cents(m.group(2))))
            continue

        m = re.match(r'(\S+): posts big blind \$([\d.]+)', line)
        if m and m.group(1) in name_to_seat:
            actions.append(Action("post_bb", seat=name_to_seat[m.group(1)], amount=_cents(m.group(2))))
            continue

        # ── Hole cards dealt ─────────────────────────────────────────────
        if section == "hole_cards":
            m = re.match(r'Dealt to (\S+)\s*(\[.*?\])?', line)
            if m and m.group(1) in name_to_seat:
                seat  = name_to_seat[m.group(1)]
                cards = _parse_cards_str(m.group(2)) if m.group(2) else []
                actions.append(Action("deal_hole", seat=seat, cards=cards))
                continue

        # ── Player actions ───────────────────────────────────────────────
        m = re.match(r'(\S+): (folds|checks)', line)
        if m and m.group(1) in name_to_seat:
            act_type = "fold" if m.group(2) == "folds" else "check"
            actions.append(Action(act_type, seat=name_to_seat[m.group(1)]))
            continue

        m = re.match(r'(\S+): calls \$([\d.]+)', line)
        if m and m.group(1) in name_to_seat:
            actions.append(Action("call", seat=name_to_seat[m.group(1)], amount=_cents(m.group(2))))
            continue

        m = re.match(r'(\S+): bets \$([\d.]+)', line)
        if m and m.group(1) in name_to_seat:
            actions.append(Action("bet", seat=name_to_seat[m.group(1)], amount=_cents(m.group(2))))
            continue

        m = re.match(r'(\S+): raises \$[\d.]+ to \$([\d.]+)', line)
        if m and m.group(1) in name_to_seat:
            # amount = the "to" value; get_state handles the delta correctly
            actions.append(Action("raise", seat=name_to_seat[m.group(1)], amount=_cents(m.group(2))))
            continue

        # ── Showdown card reveal ─────────────────────────────────────────
        m = re.match(r'(\S+): shows \[([^\]]+)\]', line)
        if m and m.group(1) in name_to_seat:
            seat  = name_to_seat[m.group(1)]
            cards = _parse_cards_str(m.group(2))
            actions.append(Action("deal_hole", seat=seat, cards=cards))
            continue

    return PokerHand(
        hand_id=hand_id,
        players=players,
        button_seat=button_seat,
        actions=actions,
        variant=variant,
        poker_site=poker_site,
        hand_date=hand_date,
        table_name=table_name,
        stakes=stakes,
    )


def parse_hands_from_text(text: str) -> List[PokerHand]:
    """Parse text containing one or more hands in generic, GG, Coin, or 888 format."""
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        return []

    # 1. Generic format
    if stripped.startswith(("Hand:", "HandID:")):
        hands = parse_generic_hand_text(stripped)
        if hands:
            return hands

    # 2. 888poker format
    if "888poker" in stripped or "#Game No" in stripped:
        try:
            from poker_888_importer import parse_888poker_hand
            blocks = stripped.split("#Game No")
            h888 = []
            for b in blocks:
                if b.strip():
                    h = parse_888poker_hand("#Game No" + b)
                    if h:
                        h888.append(h)
            if h888:
                return h888
        except Exception:
            pass

    # 3. CoinPoker format
    if "CoinPoker" in stripped or "₮" in stripped:
        try:
            from hand_checker import parse_coin_poker_text
            cp_hands = parse_coin_poker_text(stripped)
            if cp_hands:
                return cp_hands
        except Exception:
            pass

    # 4. GGPoker format / Poker Hand # format (can contain many hands)
    if "Poker Hand #" in stripped or "Poker Hand " in stripped or "RushAndCash" in stripped:
        blocks = [b.strip() for b in re.split(r'(?=^Poker Hand #?)', stripped, flags=re.M) if b.strip()]
        parsed = [_parse_single_hand(b) for b in blocks]
        valid = [h for h in parsed if h is not None]
        if valid:
            return valid

    # 5. Try generic format fallback
    hands = parse_generic_hand_text(stripped)
    if hands:
        return hands

    # 6. Fallback: split by double newlines
    blocks = [b.strip() for b in re.split(r'\n\s*\n', stripped) if b.strip()]
    parsed = [_parse_single_hand(b) for b in blocks]
    valid = [h for h in parsed if h is not None]
    if valid:
        return valid

    # 7. Single hand fallback
    single = _parse_single_hand(stripped)
    if single:
        return [single]

    return []


def parse_hand_text(text: str) -> Optional[PokerHand]:
    """Parse a single hand text block into a PokerHand."""
    hands = parse_hands_from_text(text)
    return hands[0] if hands else None


def parse_hand_file(path: Path) -> List[PokerHand]:
    """Parse a hand history file into a list of PokerHand objects."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_hands_from_text(text)
