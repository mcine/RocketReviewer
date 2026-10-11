import re
from pathlib import Path
import argparse

from generic_hand_format import serialize_poker_hand
from hand_replayer import parse_hand_text

def extract_hands(text: str):
    # Split on lines that start a hand
    parts = re.split(r'(?=^Poker Hand )', text, flags=re.M)
    return [p.strip('\n') for p in parts if p.strip()]


def hand_has_river(hand: str) -> bool:
    return bool(re.search(r'^\*+.*?\bRIVER\b.*?\*+', hand, flags=re.M | re.IGNORECASE))

def does_hero_show_hand(hand) -> bool:
    # Check if Hero shows hand in summary.
    return bool(re.search(r'^Hero: shows', hand, flags=re.M))

def get_hand_id(hand: str) -> str | None:
    m = re.search(r"Poker Hand #?([A-Za-z0-9]+)", hand)
    return m.group(1) if m else None


def hero_folded(hand: str, hero_name: str = "Hero") -> bool:
    return bool(re.search(rf'^{re.escape(hero_name)}: folds$', hand, flags=re.M))


def get_big_blind_cents(hand: str) -> int:
    """Return the big blind in cents from the hand header, or 0 if not found."""
    m = re.search(r'\(\$[\d.]+/\$([\d.]+)\)', hand)
    return round(float(m.group(1)) * 100) if m else 0


def get_total_pot_cents(poker_hand) -> int:
    """Return total pot in cents from win_pot actions."""
    return sum(a.amount for a in poker_hand.actions if a.action_type == "win_pot")



def get_total_pot_cents(poker_hand) -> int:
    """Return total pot in cents from win_pot actions."""
    return sum(a.amount for a in poker_hand.actions if a.action_type == "win_pot")


def get_winner_name(hand: str) -> str | None:
    # Prefer the pot collection line in the end section.
    m = re.search(r'^(?P<name>\S+) collected \$[\d.]+ from pot$', hand, flags=re.M)
    if m:
        return m.group('name')
    # Fallback to summary winner line.
    m = re.search(r'^Seat \d+: (?P<name>\S+) .* won .*$', hand, flags=re.M)
    return m.group('name') if m else None


def get_total_pot_cents(poker_hand) -> int:
    """Return total pot in cents from win_pot actions."""
    return sum(a.amount for a in poker_hand.actions if a.action_type == "win_pot")


def get_winner_name(hand: str) -> str | None:
    # Prefer the pot collection line in the end section.
    m = re.search(r'^(?P<name>\S+) collected \$[\d.]+ from pot$', hand, flags=re.M)
    if m:
        return m.group('name')
    # Fallback to summary winner line.
    m = re.search(r'^Seat \d+: (?P<name>\S+) .* won .*$', hand, flags=re.M)
    return m.group('name') if m else None


def get_total_pot_cents(poker_hand) -> int:
    """Return total pot in cents from win_pot actions."""
    return sum(a.amount for a in poker_hand.actions if a.action_type == "win_pot")


def get_winner_name(hand: str) -> str | None:
    # Prefer the pot collection line in the end section.
    m = re.search(r'^(?P<name>\S+) collected \$[\d.]+ from pot$', hand, flags=re.M)
    if m:
        return m.group('name')
    # Fallback to summary winner line.
    m = re.search(r'^Seat \d+: (?P<name>\S+) .* won .*$', hand, flags=re.M)
    return m.group('name') if m else None


def get_stake_names(hand: str) -> list[str]:
    """Extracts a list of descriptive stake names from the hand header based on BB."""
    stakes = []
    bb_cents = get_big_blind_cents(hand)

    if bb_cents > 0:
        stakes.append(f"NL{bb_cents}")

    return stakes


def process_files(input_dir: Path, output_dir: Path, rename_hero: bool = True) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    hero_name = "Hero"

    def replace_name(text: str, name: str, replacement: str) -> str:
        pattern = rf'(?:(?<=^)|(?<=\s)){re.escape(name)}(?=$|\s|[:;.,!?()\[\]<>"\'`~@#$%^&*\-+=\\/|])'
        return re.sub(pattern, replacement, text)

    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        if not (path.name.startswith("GG") and path.suffix.lower() == ".txt"):
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        hands = extract_hands(text)
        for hand in hands:
            if hand_has_river(hand):
                hid = get_hand_id(hand)
                if not hid:
                    continue
                is_rush_and_cash = bool(re.search(r"^Table '?RushAndCash", hand, flags=re.M))
                output_hand = hand.strip()
                if hero_folded(output_hand, hero_name) and rename_hero:
                    winner_name = get_winner_name(output_hand)
                    if winner_name:
                        #print(f"Hero folded; winner is '{winner_name}'")
                        output_hand = replace_name(output_hand, hero_name, 'tmp_player')
                        output_hand = replace_name(output_hand, winner_name, hero_name)
                        output_hand = replace_name(output_hand, 'tmp_player', winner_name)
                        if(not does_hero_show_hand(output_hand)):
                            continue
                poker_hand = parse_hand_text(output_hand)
                if not poker_hand:
                    continue
                bb_cents = get_big_blind_cents(hand)
                if bb_cents > 0 and get_total_pot_cents(poker_hand) < 25 * bb_cents:
                    continue
                poker_hand.poker_site = "GG-Poker"
                if is_rush_and_cash and poker_hand.variant:
                    poker_hand.variant += " - Fast-Fold"
                elif is_rush_and_cash:
                    poker_hand.variant = "Fast-Fold"
                poker_hand = parse_hand_text(output_hand)
                if not poker_hand:
                    continue
                bb_cents = get_big_blind_cents(hand)
                if bb_cents > 0 and get_total_pot_cents(poker_hand) < 25 * bb_cents:
                    continue
                poker_hand.poker_site = "GG-Poker"
                if is_rush_and_cash and poker_hand.variant:
                    poker_hand.variant += " - Fast-Fold"
                elif is_rush_and_cash:
                    poker_hand.variant = "Fast-Fold"

                stake_names = get_stake_names(hand)
                
                if stake_names:
                    for stake_name in stake_names:
                        sub_dir = output_dir / stake_name
                        sub_dir.mkdir(parents=True, exist_ok=True)
                        out_path = sub_dir / f"{hid}.txt"
                        out_path.write_text(serialize_poker_hand(poker_hand) + "\n", encoding='utf-8')
                else:
                    # Fallback to root output directory if no stake name is found
                    out_path = output_dir /  f"{hid}.txt"
                    out_path.write_text(serialize_poker_hand(poker_hand) + "\n", encoding='utf-8')
                written += 1

    return written


def main():
    p = argparse.ArgumentParser(
        description='Extract hands that reached the river',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python extract_river_hands.py\n"
            "  python extract_river_hands.py my_in my_out\n"
            "  python extract_river_hands.py -i in -o out\n"
        ),
    )
    p.add_argument('--input', '-i', default='input', help='Input directory')
    p.add_argument('--output', '-o', default='output', help='Output directory')
    p.add_argument('--norename', action='store_true', help='Do not rename Hero when he folded')
    p.add_argument('pos_input', nargs='?', help='Positional input directory (optional)')
    p.add_argument('pos_output', nargs='?', help='Positional output directory (optional)')
    args = p.parse_args()

    # Prefer positional args if provided, otherwise use flags/defaults
    input_dir = Path(args.pos_input) if args.pos_input else Path(args.input)
    output_dir = Path(args.pos_output) if args.pos_output else Path(args.output)

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        raise SystemExit(1)

    written = process_files(input_dir, output_dir, rename_hero=not args.norename)
    print(f"Wrote {written} hand file(s) to {output_dir}")


if __name__ == '__main__':
    main()