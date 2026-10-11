"""Generic poker hand format for the rangecheck application.

This module provides a simple, application-specific hand serialization
format that can be written by the extract script and read by the
rangecheck app.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


def _fmt_cents(amount: int) -> str:
    if amount == 0:
        return "0"
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    d, c = divmod(amount, 100)
    return f"{sign}{d}.{c:02d}" if c else f"{sign}{d}"


def _cents(value: str) -> int:
    return round(float(value.lstrip("$")) * 100)


def _parse_cards(parts: List[str]) -> List[str]:
    return [p for p in parts if re.fullmatch(r'[2-9TJQKAtjqka][shdcSHDC]', p)]


def serialize_poker_hand(hand: "PokerHand") -> str:
    lines: List[str] = [f"Hand: {hand.hand_id}"]
    if hand.variant:
        lines.append(f"Variant: {hand.variant}")
    if getattr(hand, 'poker_site', ''):
        lines.append(f"PokerSite: {hand.poker_site}")
    lines.append(f"Button: {hand.button_seat}")
    lines.append("Players:")
    for seat in sorted(hand.players):
        player = hand.players[seat]
        lines.append(f"  Seat {seat}: {player.name} ${_fmt_cents(player.stack)}")
    lines.append("Actions:")
    for action in hand.actions:
        # Omit empty preflop hole-card markers with no card list.
        if action.action_type == "deal_hole" and not action.cards:
            continue
        action_name = "holecards" if action.action_type == "deal_hole" else action.action_type
        parts: List[str] = [action_name]
        if action.seat is not None:
            parts.append(str(action.seat))
        if action.action_type in ("post_sb", "post_bb", "call", "bet", "raise", "win_pot", "return_uncalled"):
            parts.append(_fmt_cents(action.amount))
        if action.cards:
            parts.extend(action.cards)
        if action.description:
            parts.append(f"# {action.description}")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def _parse_generic_hand_block(text: str) -> Optional["PokerHand"]:
    from hand_replayer import Action, PokerHand, PokerPlayer

    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    hand_id = None
    variant = ""
    poker_site = ""
    button_seat = 1
    players: List[PokerPlayer] = []
    actions: List[Action] = []
    section = None

    for line in lines:
        line = line.strip()
        if line.startswith("Hand:") or line.startswith("HandID:"):
            hand_id = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Variant:"):
            variant = line.split(":", 1)[1].strip()
            continue
        if line.startswith("PokerSite:"):
            poker_site = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Button:"):
            button_seat = int(line.split(":", 1)[1].strip())
            continue
        if line.startswith("Players:"):
            section = "players"
            continue
        if line.startswith("Actions:"):
            section = "actions"
            continue

        if section == "players":
            m = re.match(r'^Seat\s+(\d+):\s+(.+?)\s+\$?([\d.]+)$', line)
            if not m:
                return None
            seat = int(m.group(1))
            name = m.group(2).strip()
            stack = _cents(m.group(3))
            players.append(PokerPlayer(seat=seat, name=name, stack=stack))
            continue

        if section == "actions":
            raw_line = line.split("#", 1)[0].strip()
            parts = raw_line.split()
            if not parts:
                continue
            action_type = parts[0]
            seat = None
            amount = 0
            cards: List[str] = []
            description = ""

            if action_type in ("fold", "check"):
                if len(parts) < 2:
                    return None
                seat = int(parts[1])
            elif action_type in ("post_sb", "post_bb", "call", "bet", "raise", "win_pot", "return_uncalled"):
                if len(parts) < 3:
                    return None
                seat = int(parts[1])
                amount = _cents(parts[2])
                cards = _parse_cards(parts[3:])
            elif action_type in ("deal_hole", "holecards"):
                if len(parts) < 2:
                    return None
                seat = int(parts[1])
                cards = _parse_cards(parts[2:])
                if not cards:
                    continue
                action_type = "deal_hole"
            elif action_type in ("deal_flop", "deal_turn", "deal_river"):
                cards = _parse_cards(parts[1:])
            else:
                return None

            actions.append(Action(action_type, seat=seat, amount=amount, cards=cards, description=description))
            continue

    if hand_id is None or not players:
        return None

    return PokerHand(hand_id=hand_id, players=players, button_seat=button_seat, actions=actions, variant=variant, poker_site=poker_site)


def parse_generic_hand_text(text: str) -> List["PokerHand"]:
    text = text.lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", text.strip())
    hands: List[Optional["PokerHand"]] = [_parse_generic_hand_block(block.strip()) for block in blocks if block.strip()]
    return [hand for hand in hands if hand is not None]


def write_generic_hand_file(path: Path, hands: List["PokerHand"]) -> None:
    content = "\n\n".join(serialize_poker_hand(hand) for hand in hands)
    path.write_text(content + "\n", encoding="utf-8")
