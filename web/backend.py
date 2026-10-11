"""
Backend API and Data Service for the Modern Poker Hand Replayer & Solver Reviewer.
Reuses generic_hand_format and hand_replayer from C:\\misc\\code\\rangegame.
Adds 888poker, CoinPoker, and GG-Poker conversion, file uploads, and background progress tracking.
"""
import sys
import os
import re
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_DIR = str(Path(__file__).resolve().parent.parent)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

RANGEGAME_DIR = r"C:\misc\code\rangegame"
if RANGEGAME_DIR not in sys.path:
    sys.path.append(RANGEGAME_DIR)

from generic_hand_format import parse_generic_hand_text, serialize_poker_hand, write_generic_hand_file, _fmt_cents
from hand_replayer import HandReplayer, parse_hand_file, PokerHand, Action, PokerPlayer
from solver_bridge import RocketSolverBridge
from hand_checker import load_all_test_hands, get_hero_info, get_player_position, parse_coin_poker_text, verify_hand_with_solver
from poker_888_importer import parse_888poker_file, parse_888poker_hand

CONVERTED_DIR = Path(__file__).resolve().parent.parent / "converted_hands"
CONVERTED_DIR.mkdir(exist_ok=True)
SOLVER_REVIEWS_FILE = Path(__file__).resolve().parent.parent / "solver_reviews.json"

class ReplayerService:
    def __init__(self):
        self.hands: List[PokerHand] = []
        self.review_results: Dict[str, Dict[str, Any]] = {}
        self.bridge = RocketSolverBridge()
        self._cancel_requested = False
        self._solver_active = False
        self.progress = {
            "status": "idle",
            "percent": 0,
            "message": "Ready. No hands loaded.",
            "current": 0,
            "total": 0,
            "logs": []
        }
        self.load_stored_reviews()
        # At startup/refresh: load whatever hands exist in converted_hands/ directory on disk
        self.reload_converted_hands()

    def load_stored_reviews(self):
        """Loads previously saved RocketSolver analysis results from solver_reviews.json."""
        if SOLVER_REVIEWS_FILE.exists():
            try:
                data = json.loads(SOLVER_REVIEWS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for hand_id, rev in data.items():
                        if isinstance(rev, dict) and rev.get("is_reviewed"):
                            self.review_results[hand_id] = rev
            except Exception as e:
                print(f"Warning loading solver_reviews.json: {e}")

    def save_stored_reviews(self):
        """Saves current RocketSolver analysis results to solver_reviews.json."""
        try:
            to_save = {
                k: v for k, v in self.review_results.items()
                if isinstance(v, dict) and v.get("is_reviewed")
            }
            temp_file = SOLVER_REVIEWS_FILE.with_suffix(".tmp")
            temp_file.write_text(json.dumps(to_save, indent=2), encoding="utf-8")
            temp_file.replace(SOLVER_REVIEWS_FILE)
        except Exception as e:
            print(f"Warning saving solver_reviews.json: {e}")

    def reload_converted_hands(self) -> Dict[str, Any]:
        """Loads and syncs in-memory hands with whatever is in converted_hands/ directory on disk."""
        if self.progress.get("status") == "running":
            return {"success": False, "reason": "solver_running"}
        self.load_stored_reviews()
        loaded_hands = []
        if CONVERTED_DIR.exists():
            for f in sorted(CONVERTED_DIR.glob("*.txt")):
                try:
                    parsed = parse_generic_hand_text(f.read_text(encoding="utf-8"))
                    loaded_hands.extend(parsed)
                except Exception as e:
                    print(f"Error loading {f}: {e}")
        self.hands = loaded_hands
        self.run_initial_analysis()
        if len(self.hands) > 0:
            self.set_progress("idle", 100, f"Ready. {len(self.hands)} hands loaded from disk.", len(self.hands), len(self.hands))
        else:
            self.set_progress("idle", 0, "Ready. No hands loaded.", 0, 0)
        return {"success": True, "count": len(self.hands)}

    load_converted_from_disk = reload_converted_hands

    def set_progress(self, status: str, percent: int, message: str, current: int = 0, total: int = 0, log_line: str = None):
        self.progress["status"] = status
        self.progress["percent"] = percent
        self.progress["message"] = message
        self.progress["current"] = current
        self.progress["total"] = total
        if log_line:
            self.progress["logs"].append(log_line)
            if len(self.progress["logs"]) > 200:
                self.progress["logs"].pop(0)

    def load_default_hands(self):
        """Loads all test hands from rangegame data/nltest, 888poker samples, and input/."""
        self.set_progress("importing", 10, "Loading default hand histories...", 0, 0)
        self.hands = []

        # 1. Rangegame nltest hands
        test_dir = Path(r"C:\misc\code\rangegame\data\nltest")
        if test_dir.exists():
            for f in sorted(test_dir.glob("*.txt")):
                try:
                    loaded = parse_hand_file(f)
                    self.hands.extend(loaded)
                except Exception as e:
                    print(f"Error loading {f}: {e}")

        # 2. 888poker sample hands
        p888_dir = Path(r"C:\misc\888poker_hand_history\Sharkendahl")
        if p888_dir.exists():
            for f in sorted(p888_dir.glob("*.txt"))[:4]: # Load first 4 sample files
                try:
                    loaded = parse_888poker_file(f)
                    self.hands.extend(loaded)
                except Exception as e:
                    print(f"Error loading 888poker file {f}: {e}")

        # Convert and cache in custom generic format
        self.save_converted_hands()
        self.run_initial_analysis()
        self.set_progress("idle", 100, f"Ready. {len(self.hands)} hands loaded.", len(self.hands), len(self.hands))

    def save_converted_hands(self):
        """Converts and writes all loaded hands to the custom generic format."""
        try:
            for hand in self.hands:
                dest = CONVERTED_DIR / f"{hand.hand_id}.txt"
                content = serialize_poker_hand(hand)
                dest.write_text(content + "\n", encoding="utf-8")
        except Exception as e:
            print(f"Warning saving converted hand: {e}")

    def run_initial_analysis(self):
        """Initializes hands in 'not_reviewed' state. GTO OK and Review statuses are set only after running RocketSolver."""
        for hand in self.hands:
            if hand.hand_id in self.review_results and self.review_results[hand.hand_id].get("is_reviewed"):
                rev = self.review_results[hand.hand_id]
                hero_seat = rev.get("hero_seat")
                if hero_seat is None:
                    hero_seat, _, _ = get_hero_info(hand)
                    rev["hero_seat"] = hero_seat
                rev["hero_net_cents"] = self._compute_hero_profit(hand, hero_seat)
                continue
            hero_seat, hero_pos, hero_cards = get_hero_info(hand)
            hero_net = self._compute_hero_profit(hand, hero_seat)
            board = []
            for a in hand.actions:
                if a.action_type in ("deal_flop", "deal_turn", "deal_river"):
                    board.extend(a.cards)
            self.review_results[hand.hand_id] = {
                "hand_id": hand.hand_id,
                "variant": hand.variant or "No-Limit Hold'em",
                "poker_site": getattr(hand, "poker_site", "Unknown"),
                "hero_seat": hero_seat,
                "hero_pos": hero_pos,
                "hero_cards": hero_cards,
                "board": board,
                "hero_net_cents": hero_net,
                "is_reviewed": False,
                "review_status": "not_reviewed",
                "marked_for_review": False,
                "review_reasons": [],
                "street_analyses": []
            }


    def _compute_hero_profit(self, hand: PokerHand, hero_seat: Optional[int]) -> int:
        if not hero_seat or hero_seat not in hand.players:
            return 0
        try:
            replayer = HandReplayer()
            replayer.load_hands([hand])
            if hand.display_steps:
                replayer.display_index = len(hand.display_steps) - 1
                st = replayer.get_state()
                initial_stack = hand.players[hero_seat].stack
                final_stack = st['player_stacks'].get(hero_seat, initial_stack)
                return final_stack - initial_stack
        except Exception:
            pass
        return 0

    def _extract_meta(self, hand: PokerHand, session_idx: int = 1, session_start_dt: Optional[datetime] = None) -> Dict[str, Any]:
        site = getattr(hand, "poker_site", "") or "Online"
        raw_date = getattr(hand, "hand_date", "") or ""
        stakes_str = getattr(hand, "stakes", "")
        table_str = getattr(hand, "table_name", "")
        game_type = getattr(hand, "game_type", "")

        # Infer blinds/stakes if not explicitly set
        if not stakes_str:
            sb_amt = next((a.amount for a in hand.actions if a.action_type == "post_sb"), None)
            bb_amt = next((a.amount for a in hand.actions if a.action_type == "post_bb"), None)
            if sb_amt is not None and bb_amt is not None:
                stakes_str = f"${_fmt_cents(sb_amt)} / ${_fmt_cents(bb_amt)}"
            elif bb_amt is not None:
                stakes_str = f"BB ${_fmt_cents(bb_amt)}"
            else:
                stakes_str = "No Limit"

        # Date & Time parsing
        date_str = ""
        time_str = ""
        hand_dt: Optional[datetime] = None

        m_date = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})\s+([\d:]+)', raw_date)
        if m_date:
            try:
                hand_dt = datetime.strptime(f"{m_date.group(3)}-{m_date.group(2)}-{m_date.group(1)} {m_date.group(4)}", "%Y-%m-%d %H:%M:%S")
                date_str = f"{m_date.group(3)}/{m_date.group(2)}/{m_date.group(1)}"
                time_str = m_date.group(4)
            except Exception:
                pass

        if not date_str:
            m_iso = re.search(r'(20\d{2})[-/_]?(\d{2})[-/_]?(\d{2})(?:\s+([\d:]+))?', raw_date or hand.hand_id)
            if m_iso:
                date_str = f"{m_iso.group(1)}/{m_iso.group(2)}/{m_iso.group(3)}"
                time_str = m_iso.group(4) or ""
            else:
                date_str = "2026/06/15"

        # Elapsed session time calculation
        elapsed_str = ""
        if hand_dt and session_start_dt:
            diff_secs = max(0, int((hand_dt - session_start_dt).total_seconds()))
            elapsed_str = f"+{diff_secs // 60:02d}:{diff_secs % 60:02d}"

        # Human-useful Hand Number
        m_num = re.search(r'(\d{5,})', hand.hand_id)
        if m_num:
            hand_num = m_num.group(1)
        elif "REVIEW" in hand.hand_id.upper():
            m_rev = re.search(r'(\d+)', hand.hand_id)
            hand_num = f"Mistake #{m_rev.group(1)}" if m_rev else "Mistake Demo"
        else:
            hand_num = str(session_idx)

        # Human-useful Display Title
        if time_str and m_num:
            display_title = f"Hand #{hand_num} • {time_str}"
        elif m_num:
            display_title = f"Hand #{session_idx} • #{hand_num}"
        elif "Mistake" in hand_num:
            display_title = f"Review Hand #{session_idx} ({hand_num})"
        else:
            display_title = f"Hand #{session_idx}"

        # Human-useful Display Date (for date/time badge, without duplicating stakes)
        if time_str:
            display_date = f"{date_str} {time_str}"
        elif elapsed_str:
            display_date = f"{date_str} (T{elapsed_str})"
        else:
            display_date = date_str

        # Human-useful Display Subtitle
        if elapsed_str:
            display_subtitle = f"Session T{elapsed_str} • {date_str} • {stakes_str}"
        elif time_str:
            display_subtitle = f"{date_str} {time_str} • {stakes_str}"
        else:
            display_subtitle = f"{date_str} • {stakes_str}"

        if not table_str:
            table_str = f"{len(hand.players)}-Max Table"

        if not game_type:
            game_type = "Tournament" if "Tournament" in (hand.variant or "") else "Cash Game"

        return {
            "poker_site": site,
            "hand_date": date_str,
            "hand_time": time_str,
            "display_date": display_date,
            "session_elapsed": elapsed_str,
            "session_index": session_idx,
            "hand_number": hand_num,
            "display_title": display_title,
            "display_subtitle": display_subtitle,
            "stakes": stakes_str,
            "table_name": table_str,
            "game_type": game_type
        }

    def compute_total_pot_cents(self, hand: PokerHand) -> int:
        total_pot = sum(a.amount for a in hand.actions if a.action_type == "win_pot")
        if total_pot == 0:
            total_pot = sum(a.amount for a in hand.actions if a.action_type in ("bet", "call", "post_sb", "post_bb", "raise"))
        return total_pot

    def _is_hand_run_it_twice(self, hand: PokerHand) -> bool:
        deal_types = [a.action_type for a in hand.actions if a.action_type in ("deal_flop", "deal_turn", "deal_river")]
        return (deal_types.count("deal_flop") > 1 or 
                deal_types.count("deal_turn") > 1 or 
                deal_types.count("deal_river") > 1)

    def _analyze_run_it_twice(self, hand: PokerHand) -> Dict[str, Any]:
        """
        Analyzes whether the hand has Run It Twice (RIT) deals, and categorizes
        all deal actions into:
          - is_run_twice: bool
          - shared_actions: list of Action objects whose cards are shared across both runs
          - run1_actions: list of Action objects belonging to Run 1
          - run2_actions: list of Action objects belonging to Run 2
        """
        flop_acts = [a for a in hand.actions if a.action_type == "deal_flop"]
        turn_acts = [a for a in hand.actions if a.action_type == "deal_turn"]
        river_acts = [a for a in hand.actions if a.action_type == "deal_river"]

        is_rit = (len(flop_acts) > 1 or len(turn_acts) > 1 or len(river_acts) > 1)
        if not is_rit:
            return {
                "is_run_twice": False,
                "shared_actions": flop_acts + turn_acts + river_acts,
                "run1_actions": [],
                "run2_actions": []
            }

        shared_actions = []
        run1_actions = []
        run2_actions = []

        # Flop
        if len(flop_acts) > 1:
            run1_actions.append(flop_acts[0])
            run2_actions.append(flop_acts[1])
        elif len(flop_acts) == 1:
            shared_actions.append(flop_acts[0])

        # Turn
        if len(turn_acts) > 1:
            run1_actions.append(turn_acts[0])
            run2_actions.append(turn_acts[1])
        elif len(turn_acts) == 1:
            if len(flop_acts) > 1:
                run1_actions.append(turn_acts[0])
            else:
                shared_actions.append(turn_acts[0])

        # River
        if len(river_acts) > 1:
            run1_actions.append(river_acts[0])
            run2_actions.append(river_acts[1])
        elif len(river_acts) == 1:
            if len(flop_acts) > 1 or len(turn_acts) > 1:
                run1_actions.append(river_acts[0])
            else:
                shared_actions.append(river_acts[0])

        return {
            "is_run_twice": True,
            "shared_actions": shared_actions,
            "run1_actions": run1_actions,
            "run2_actions": run2_actions
        }

    def get_hands_list(self) -> List[Dict[str, Any]]:
        # Compute session start datetime if timestamped hands are present
        session_start_dt: Optional[datetime] = None
        for h in self.hands:
            raw = getattr(h, "hand_date", "") or ""
            m_date = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})\s+([\d:]+)', raw)
            if m_date:
                try:
                    dt = datetime.strptime(f"{m_date.group(3)}-{m_date.group(2)}-{m_date.group(1)} {m_date.group(4)}", "%Y-%m-%d %H:%M:%S")
                    if session_start_dt is None or dt < session_start_dt:
                        session_start_dt = dt
                except Exception:
                    pass

        result = []
        for idx, hand in enumerate(self.hands):
            rev = self.review_results.get(hand.hand_id, {})
            meta = self._extract_meta(hand, session_idx=idx+1, session_start_dt=session_start_dt)
            total_pot = self.compute_total_pot_cents(hand)

            net = rev.get("hero_net_cents", 0)
            if net > 0:
                hero_net_formatted = f"+${_fmt_cents(net)}"
                is_win = True
                is_loss = False
            elif net < 0:
                hero_net_formatted = f"-${_fmt_cents(abs(net))}"
                is_win = False
                is_loss = True
            else:
                hero_net_formatted = "$0.00"
                is_win = False
                is_loss = False

            result.append({
                "hand_id": hand.hand_id,
                "variant": hand.variant or "No-Limit Hold'em",
                "poker_site": meta["poker_site"],
                "hand_date": meta["hand_date"],
                "hand_time": meta["hand_time"],
                "session_elapsed": meta["session_elapsed"],
                "session_index": meta["session_index"],
                "hand_number": meta["hand_number"],
                "display_title": meta["display_title"],
                "display_subtitle": meta["display_subtitle"],
                "stakes": meta["stakes"],
                "table_name": meta["table_name"],
                "game_type": meta["game_type"],
                "is_run_twice": self._is_hand_run_it_twice(hand),
                "players_count": len(hand.players),
                "hero_seat": rev.get("hero_seat"),
                "hero_pos": rev.get("hero_pos", ""),
                "hero_cards": rev.get("hero_cards", []),
                "hero_net_cents": net,
                "hero_net_formatted": hero_net_formatted,
                "hero_is_win": is_win,
                "hero_is_loss": is_loss,
                "total_pot_cents": total_pot,
                "total_pot_formatted": f"${_fmt_cents(total_pot)}",
                "is_reviewed": rev.get("is_reviewed", False),
                "review_status": rev.get("review_status", "not_reviewed"),
                "marked_for_review": rev.get("marked_for_review", False),
                "review_reasons": rev.get("review_reasons", [])
            })
        return result

    def get_hand_details(self, hand_id: str) -> Optional[Dict[str, Any]]:
        hand = next((h for h in self.hands if h.hand_id == hand_id), None)
        if not hand:
            return None

        rev = self.review_results.get(hand.hand_id, {})
        replayer = HandReplayer()
        replayer.load_hands([hand])

        # Gather any revealed/known hole cards across all actions (showdowns, deal_hole, etc.)
        known_seat_cards: Dict[int, List[str]] = {}
        for act in hand.actions:
            if act.cards and act.seat is not None and act.action_type in ("deal_hole", "holecards", "win_pot"):
                if act.cards != ["back", "back"]:
                    known_seat_cards[act.seat] = act.cards

        steps_data = []
        total_display_steps = len(hand.display_steps)
        rit_info = self._analyze_run_it_twice(hand)

        for i in range(total_display_steps):
            is_last_step = (i == total_display_steps - 1)
            replayer.display_index = i
            st = replayer.get_state()

            raw_idx = hand.display_steps[i] - 1
            last_act = hand.actions[raw_idx] if 0 <= raw_idx < len(hand.actions) else None
            step_actions = hand.actions[:raw_idx + 1] if 0 <= raw_idx < len(hand.actions) else []
            
            act_desc = ""
            acting_seat = None
            action_bubble = None

            if last_act:
                p = hand.players.get(last_act.seat)
                p_name = p.name if p else f"Seat {last_act.seat}"
                t = last_act.action_type
                amt = last_act.amount or 0
                amt_str = f"${_fmt_cents(amt)}" if amt > 0 else ""

                if last_act.seat and t in ("post_sb", "post_bb", "fold", "check", "call", "bet", "raise", "win_pot"):
                    acting_seat = last_act.seat
                    p_stack = st['player_stacks'].get(last_act.seat, 0)
                    is_all_in = (p_stack == 0) and (t in ("bet", "raise", "call"))

                    if is_all_in:
                        bubble_text = f"ALL-IN {amt_str}".strip()
                    elif t == "fold":
                        bubble_text = "FOLD"
                    elif t == "check":
                        bubble_text = "CHECK"
                    elif t == "call":
                        bubble_text = f"CALL {amt_str}".strip()
                    elif t == "bet":
                        bubble_text = f"BET {amt_str}".strip()
                    elif t == "raise":
                        bubble_text = f"RAISE {amt_str}".strip()
                    elif t == "post_sb":
                        bubble_text = f"SB {amt_str}".strip()
                    elif t == "post_bb":
                        bubble_text = f"BB {amt_str}".strip()
                    elif t == "win_pot":
                        bubble_text = f"WON {amt_str}".strip()
                    else:
                        bubble_text = t.upper()

                    action_bubble = {
                        "seat": last_act.seat,
                        "action_type": "all_in" if is_all_in else t,
                        "amount": amt_str,
                        "text": bubble_text,
                        "is_all_in": is_all_in
                    }

                if t in ("post_sb", "post_bb"):
                    act_desc = f"{p_name} posts {'SB' if t == 'post_sb' else 'BB'} {amt_str}"
                elif t == "fold":
                    act_desc = f"{p_name} folds"
                elif t == "check":
                    act_desc = f"{p_name} checks"
                elif t == "call":
                    act_desc = f"{p_name} calls {amt_str}"
                elif t == "bet":
                    act_desc = f"{p_name} bets {amt_str}"
                elif t == "raise":
                    act_desc = f"{p_name} raises to {amt_str}"
                elif t == "deal_flop":
                    if any(id(last_act) == id(x) for x in rit_info["run1_actions"]):
                        act_desc = f"Flop (Run 1): {' '.join(last_act.cards)}"
                    elif any(id(last_act) == id(x) for x in rit_info["run2_actions"]):
                        act_desc = f"Flop (Run 2): {' '.join(last_act.cards)}"
                    else:
                        act_desc = f"Flop: {' '.join(last_act.cards)}"
                elif t == "deal_turn":
                    if any(id(last_act) == id(x) for x in rit_info["run1_actions"]):
                        act_desc = f"Turn (Run 1): {' '.join(last_act.cards)}"
                    elif any(id(last_act) == id(x) for x in rit_info["run2_actions"]):
                        act_desc = f"Turn (Run 2): {' '.join(last_act.cards)}"
                    else:
                        act_desc = f"Turn: {' '.join(last_act.cards)}"
                elif t == "deal_river":
                    if any(id(last_act) == id(x) for x in rit_info["run1_actions"]):
                        act_desc = f"River (Run 1): {' '.join(last_act.cards)}"
                    elif any(id(last_act) == id(x) for x in rit_info["run2_actions"]):
                        act_desc = f"River (Run 2): {' '.join(last_act.cards)}"
                    else:
                        act_desc = f"River: {' '.join(last_act.cards)}"
                elif t == "win_pot":
                    win_acts = [a for a in hand.actions if a.action_type == "win_pot"]
                    if rit_info["is_run_twice"] and len(win_acts) == 2:
                        p1 = hand.players.get(win_acts[0].seat)
                        p2 = hand.players.get(win_acts[1].seat)
                        p1_name = p1.name if p1 else f"Seat {win_acts[0].seat}"
                        p2_name = p2.name if p2 else f"Seat {win_acts[1].seat}"
                        amt1_str = f"${_fmt_cents(win_acts[0].amount)}"
                        amt2_str = f"${_fmt_cents(win_acts[1].amount)}"
                        if win_acts[0].seat == win_acts[1].seat:
                            tot_str = f"${_fmt_cents(win_acts[0].amount + win_acts[1].amount)}"
                            act_desc = f"{p1_name} wins both runouts for {tot_str} ({amt1_str} + {amt2_str})"
                        else:
                            act_desc = f"Split pot: {p1_name} wins Run 1 ({amt1_str}), {p2_name} wins Run 2 ({amt2_str})"
                    else:
                        act_desc = f"{p_name} wins pot {amt_str}"

            players_data = []
            for s in sorted(hand.players.keys()):
                p = hand.players[s]
                pos = get_player_position(hand, s)
                is_actor = (s == acting_seat)
                is_hero = (p.name.lower() == "hero" or s == rev.get("hero_seat"))

                raw_cards = st['player_cards'].get(s, [])
                if is_hero:
                    card_list = raw_cards if raw_cards else rev.get("hero_cards", [])
                else:
                    if (is_last_step or (raw_cards and raw_cards != ["back", "back"])) and s in known_seat_cards:
                        card_list = known_seat_cards[s]
                    elif raw_cards:
                        card_list = raw_cards
                    else:
                        card_list = known_seat_cards.get(s, []) if is_last_step else []

                players_data.append({
                    "seat": s,
                    "name": p.name,
                    "pos": pos,
                    "is_hero": is_hero,
                    "is_button": s == hand.button_seat,
                    "stack": f"${_fmt_cents(st['player_stacks'].get(s, p.stack))}",
                    "current_bet": f"${_fmt_cents(st['player_bets'].get(s, 0))}",
                    "is_active": st['player_active'].get(s, True),
                    "cards": card_list,
                    "known_cards": known_seat_cards.get(s, []),
                    "action_label": st['player_labels'].get(s, ""),
                    "is_acting_now": is_actor,
                    "bubble": action_bubble if is_actor else None
                })

            step_shared = [c for act in rit_info["shared_actions"] if any(id(act) == id(x) for x in step_actions) for c in act.cards]
            step_run1 = [c for act in rit_info["run1_actions"] if any(id(act) == id(x) for x in step_actions) for c in act.cards]
            step_run2 = [c for act in rit_info["run2_actions"] if any(id(act) == id(x) for x in step_actions) for c in act.cards]
            is_step_rit = bool(rit_info["is_run_twice"] and (step_run1 or step_run2))

            step_street = "showdown" if (hand.display_step_labels[i] == "showdown" or st["display_street"] == "SHOWDOWN") else st["street"]

            steps_data.append({
                "step_index": i,
                "step_label": hand.display_step_labels[i],
                "street": step_street,
                "display_street": st["display_street"],
                "pot": f"${_fmt_cents(st['pot'])}",
                "board": st["board"],
                "is_run_twice": is_step_rit,
                "shared_board": step_shared,
                "run1_board": step_run1,
                "run2_board": step_run2,
                "action_desc": act_desc,
                "acting_seat": acting_seat,
                "action_bubble": action_bubble,
                "players": players_data
            })

        meta = self._extract_meta(hand)
        net = rev.get("hero_net_cents", 0)
        if net > 0:
            hero_net_formatted = f"+${_fmt_cents(net)}"
            is_win = True
            is_loss = False
        elif net < 0:
            hero_net_formatted = f"-${_fmt_cents(abs(net))}"
            is_win = False
            is_loss = True
        else:
            hero_net_formatted = "$0.00"
            is_win = False
            is_loss = False

        total_pot = self.compute_total_pot_cents(hand)

        return {
            "hand_id": hand.hand_id,
            "display_title": meta["display_title"],
            "display_subtitle": meta["display_subtitle"],
            "display_date": meta["display_date"],
            "hand_number": meta["hand_number"],
            "hand_time": meta["hand_time"],
            "session_elapsed": meta["session_elapsed"],
            "hero_net_cents": net,
            "hero_net_formatted": hero_net_formatted,
            "hero_is_win": is_win,
            "hero_is_loss": is_loss,
            "total_pot_cents": total_pot,
            "total_pot_formatted": f"${_fmt_cents(total_pot)}",
            "is_run_twice": rit_info["is_run_twice"],
            "variant": hand.variant or "No-Limit Hold'em",
            "poker_site": meta["poker_site"],
            "hand_date": meta["hand_date"],
            "stakes": meta["stakes"],
            "table_name": meta["table_name"],
            "game_type": meta["game_type"],
            "button_seat": hand.button_seat,
            "hero_seat": rev.get("hero_seat"),
            "hero_pos": rev.get("hero_pos"),
            "hero_cards": rev.get("hero_cards", []),
            "is_reviewed": rev.get("is_reviewed", False),
            "review_status": rev.get("review_status", "not_reviewed"),
            "marked_for_review": rev.get("marked_for_review", False),
            "review_reasons": rev.get("review_reasons", []),
            "street_analyses": rev.get("street_analyses", []),
            "known_player_cards": {str(s): cards for s, cards in known_seat_cards.items()},
            "total_steps": len(steps_data),
            "steps": steps_data
        }

    def cancel_solver_check(self) -> Dict[str, Any]:
        """Cancels an in-progress solver check or single-hand step."""
        if self.progress.get("status") in ("running", "stepping") or self._solver_active:
            self._cancel_requested = True
            self.bridge.cancel()
            self.set_progress(
                "cancelling",
                self.progress.get("percent", 0),
                "Cancelling RocketSolver operation...",
                self.progress.get("current", 0),
                self.progress.get("total", 0),
                "[CANCEL] User requested cancellation. Stopping RocketSolver..."
            )
            return {"success": True, "message": "Cancellation requested"}
        return {"success": False, "message": "No solver task currently running"}

    def step_single_hand_in_solver(self, hand_id: str) -> Dict[str, Any]:
        """Steps through a specific hand live in RocketSolver action-by-action."""
        hand = next((h for h in self.hands if h.hand_id == hand_id), None)
        if not hand:
            return {"success": False, "error": f"Hand {hand_id} not found"}

        if not self.bridge.ensure_ready():
            return {"success": False, "error": "RocketSolver.exe is not running or window not found"}

        self.bridge.ensure_strategy_tab()
        self._solver_active = True
        self._cancel_requested = False
        self.bridge.reset_cancel()
        self.set_progress("stepping", 50, f"Stepping hand {hand_id} live in RocketSolver...", 1, 1, f"Stepping hand {hand_id} in RocketSolver...")

        try:
            step_res = self.bridge.step_hand(
                hand,
                visual_delay=0.45,
                stop_on_error=False,
                reset_at_end=False,
                cancel_check=lambda: self._cancel_requested or self.bridge.is_cancelled()
            )
            if step_res.get("cancelled") or self._cancel_requested or self.bridge.is_cancelled():
                self.set_progress("idle", 100, "Stepping cancelled by user (Escape key / Cancel button).", 1, 1, "[CANCELLED] Stepping cancelled by user.")
                return {"success": False, "cancelled": True, "error": "Operation cancelled by user"}

            hero_seat, hero_pos, hero_cards = get_hero_info(hand)
            hero_net = self._compute_hero_profit(hand, hero_seat)

            board = []
            for a in hand.actions:
                if a.action_type in ("deal_flop", "deal_turn", "deal_river"):
                    board.extend(a.cards)

            is_blunder = step_res.get("marked_for_review", False)
            rev = {
                "hand_id": hand.hand_id,
                "variant": hand.variant or "No-Limit Hold'em",
                "poker_site": getattr(hand, "poker_site", "Unknown"),
                "hero_seat": hero_seat,
                "hero_pos": hero_pos,
                "hero_cards": hero_cards,
                "board": board,
                "hero_net_cents": hero_net,
                "is_reviewed": True,
                "review_status": "review" if is_blunder else "gto_ok",
                "marked_for_review": is_blunder,
                "review_reasons": step_res.get("review_reasons", []),
                "street_analyses": step_res.get("street_analyses", [])
            }
            self.review_results[hand.hand_id] = rev
            self.save_stored_reviews()
            self.set_progress("idle", 100, f"Finished stepping hand {hand_id}.", 1, 1, f"Hand {hand_id} stepped and saved.")

            return {
                "success": True,
                "hand_id": hand_id,
                "is_reviewed": True,
                "review_status": rev["review_status"],
                "marked_for_review": rev["marked_for_review"],
                "review_reasons": rev["review_reasons"],
                "street_analyses": rev["street_analyses"]
            }
        finally:
            self._solver_active = False
            self.bridge.reset_cancel()

    def start_background_solver_check(self, hand_ids: Optional[List[str]] = None, min_hero_net_cents: Optional[int] = None, net_mode: str = "any", skip_reviewed: bool = True):
        """Starts solver check in a dedicated thread to report live progress."""
        if self.progress.get("status") in ("running", "stepping") or self._solver_active:
            return {"status": "already_running"}
        self._cancel_requested = False
        self.bridge.reset_cancel()
        self.set_progress("running", 2, "Connecting to RocketSolver...")
        t = threading.Thread(
            target=self._run_solver_check_worker,
            args=(hand_ids, min_hero_net_cents, net_mode, skip_reviewed),
            daemon=True
        )
        t.start()
        return {"status": "started"}

    def _run_solver_check_worker(self, hand_ids: Optional[List[str]] = None, min_hero_net_cents: Optional[int] = None, net_mode: str = "any", skip_reviewed: bool = True):
        self._solver_active = True
        self._cancel_requested = False
        self.bridge.reset_cancel()
        solver_available = bool(self.bridge.find_window())
        self.progress["logs"] = []

        # 1. Determine target hands based on filter (by hand_ids or by hero net won/lost)
        target_hands = list(self.hands)
        if hand_ids is not None:
            hand_id_set = set(hand_ids)
            target_hands = [h for h in target_hands if h.hand_id in hand_id_set]
        elif min_hero_net_cents is not None:
            filtered = []
            for h in target_hands:
                rev = self.review_results.get(h.hand_id, {})
                hero_seat = rev.get("hero_seat")
                if hero_seat is None:
                    hero_seat, _, _ = get_hero_info(h)
                net = rev.get("hero_net_cents")
                if net is None:
                    net = self._compute_hero_profit(h, hero_seat)
                if net_mode == "loss":
                    match = (-net) >= min_hero_net_cents
                elif net_mode == "win":
                    match = net >= min_hero_net_cents
                else: # "any" (won or lost)
                    match = abs(net) >= min_hero_net_cents
                if match:
                    filtered.append(h)
            target_hands = filtered

        total_target = len(target_hands)
        if total_target == 0:
            self.set_progress("idle", 100, "No hands match the filter to check.", 0, 0, "No hands matched the active filter.")
            self._solver_active = False
            return

        # 2. Filter out already reviewed hands if skip_reviewed is True
        # Note: If checking a single hand explicitly (e.g. user clicked "Review Hand"), never skip it!
        is_single_hand_check = bool(hand_ids is not None and len(hand_ids) == 1)
        effective_skip = skip_reviewed and not is_single_hand_check

        skipped_count = 0
        hands_to_check = []
        for h in target_hands:
            is_already_reviewed = bool(self.review_results.get(h.hand_id, {}).get("is_reviewed"))
            if effective_skip and is_already_reviewed:
                skipped_count += 1
            else:
                hands_to_check.append(h)

        if len(hands_to_check) == 0:
            msg = f"All {total_target} filtered hands have already been checked! Skipped all."
            self.set_progress("idle", 100, msg, total_target, total_target, msg)
            self._solver_active = False
            return

        if is_single_hand_check:
            init_msg = f"Re-reviewing hand {hands_to_check[0].hand_id} with RocketSolver..."
        else:
            init_msg = f"Filtered {total_target} hands: {skipped_count} already checked (skipped), {len(hands_to_check)} to analyze."

        if not solver_available:
            self.set_progress("running", 5, f"RocketSolver not detected. Performing GTO check on {len(hands_to_check)} hands...", 0, len(hands_to_check), init_msg)
            self.progress["logs"].append("RocketSolver not running - using GTO verification rules.")
        else:
            self.set_progress("running", 5, f"Connected to RocketSolver. Checking {len(hands_to_check)} hands...", 0, len(hands_to_check), init_msg)
            self.progress["logs"].append("Connected to RocketSolver.exe in background mode.")
            # Calibrate colors from Settings view on first run
            if not self.bridge.calibrated_colors:
                self.progress["logs"].append("Calibrating action colors from RocketSolver Settings...")
                colors = self.bridge.calibrate_colors()
                self.progress["logs"].append(
                    f"Action colors calibrated: Fold {colors['fold']}, Check {colors['check']}, "
                    f"BetSmall {colors['bet_small']}, BetBig {colors['bet_big']}"
                )
            self.bridge.ensure_strategy_tab()

        if skipped_count > 0:
            self.progress["logs"].append(f"[SKIPPED] {skipped_count} hands were already reviewed previously and skipped.")

        reviewed_flagged_count = 0
        total_to_check = len(hands_to_check)
        processed_count = 0

        try:
            for idx, hand in enumerate(hands_to_check):
                if self._cancel_requested or self.bridge.is_cancelled():
                    self._cancel_requested = True
                    self.progress["logs"].append("[CANCELLED] Solver check stopped by user (Escape key / Cancel button).")
                    break

                pct = int(10 + (idx / total_to_check) * 85)
                hero_seat, hero_pos, hero_cards = get_hero_info(hand)
                card_str = " ".join(hero_cards) if hero_cards else "--"
                rev_cached = self.review_results.get(hand.hand_id, {})
                net = rev_cached.get("hero_net_cents", 0)
                net_str = f"+${_fmt_cents(net)}" if net > 0 else (f"-${_fmt_cents(abs(net))}" if net < 0 else "$0.00")

                skipped_info = f" ({skipped_count} skipped)" if skipped_count > 0 else ""
                self.set_progress(
                    "running", pct,
                    f"Checking Hand {idx+1}/{total_to_check}: {hand.hand_id} ({hero_pos} {card_str}, Hero {net_str}){skipped_info}",
                    idx + 1, total_to_check,
                    f"Analyzing {hand.hand_id} (Hero: {hero_pos}, Cards: {card_str}, Hero Net: {net_str}) against RocketSolver GTO..."
                )

                # Perform live verification with solver bridge if available
                rev = verify_hand_with_solver(hand, self.bridge if solver_available else None, cancel_check=lambda: self._cancel_requested or self.bridge.is_cancelled())
                if self._cancel_requested or self.bridge.is_cancelled() or rev.get("cancelled"):
                    self._cancel_requested = True
                    self.progress["logs"].append(f"[CANCELLED] Solver check stopped during hand {hand.hand_id} (Escape key / Cancel button).")
                    break

                hero_net = self._compute_hero_profit(hand, rev.get("hero_seat"))
                rev["hero_net_cents"] = hero_net
                rev["is_reviewed"] = True
                rev["review_status"] = "review" if rev.get("marked_for_review") else "gto_ok"
                self.review_results[hand.hand_id] = rev
                self.save_stored_reviews()
                processed_count += 1

                time.sleep(0.1)

                if rev.get("marked_for_review"):
                    reviewed_flagged_count += 1
                    for r in rev.get("review_reasons", []):
                        self.set_progress("running", pct, f"Flagged Hand {hand.hand_id}", idx+1, total_to_check, f"  [FLAGGED] {r['explanation']}")
                else:
                    self.set_progress("running", pct, f"Passed Hand {hand.hand_id}", idx+1, total_to_check, f"  [PASSED] Hand {hand.hand_id} conforms to RocketSolver GTO strategy.")
        finally:
            # Leave hand in RocketSolver after review; reset happens before the next hand/review
            self._solver_active = False
            self.bridge.reset_cancel()

        self.save_stored_reviews()
        if self._cancel_requested:
            final_msg = f"Cancelled by user. Analyzed {processed_count} of {total_to_check} hands ({reviewed_flagged_count} flagged)."
            self.set_progress("idle", 100, final_msg, processed_count, total_to_check, f"[CANCELLED] {final_msg}")
            self._cancel_requested = False
        else:
            if is_single_hand_check:
                status_str = "flagged for review" if reviewed_flagged_count > 0 else "GTO validated"
                final_msg = f"Hand {hands_to_check[0].hand_id} re-reviewed: {status_str}."
                self.set_progress("idle", 100, final_msg, 1, 1, f"Review completed: Hand {hands_to_check[0].hand_id} {status_str}.")
            else:
                final_msg = f"Completed analysis of {total_to_check} hands ({reviewed_flagged_count} flagged). {skipped_count} already checked hands skipped."
                self.set_progress("idle", 100, final_msg, total_to_check, total_to_check, f"Finished! {reviewed_flagged_count} hands flagged for review. {skipped_count} previously checked hands skipped.")

            if solver_available:
                self.bridge.minimize()
                self.progress["logs"].append("Hand checks completed. RocketSolver minimized.")

    def delete_hand(self, hand_id: str) -> Dict[str, Any]:
        """Deletes a single hand by ID from memory and converted files."""
        initial_len = len(self.hands)
        self.hands = [h for h in self.hands if h.hand_id != hand_id]
        if hand_id in self.review_results:
            del self.review_results[hand_id]
            self.save_stored_reviews()

        # Delete converted file if exists
        file_path = CONVERTED_DIR / f"{hand_id}.txt"
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Warning deleting converted file: {e}")

        deleted = len(self.hands) < initial_len
        return {"success": deleted, "remaining_count": len(self.hands)}

    def clear_all_hands(self) -> Dict[str, Any]:
        """Clears all hands from memory, deletes all converted files in converted_hands/, and clears solver_reviews.json on disk."""
        count = len(self.hands)
        self.hands = []
        self.review_results = {}
        self.set_progress("idle", 0, "Ready. No hands loaded.", 0, 0)

        # Clear solver_reviews.json on disk
        cleared_solver_reviews = False
        try:
            SOLVER_REVIEWS_FILE.write_text("{}", encoding="utf-8")
            cleared_solver_reviews = True
        except Exception as e:
            print(f"Error clearing {SOLVER_REVIEWS_FILE}: {e}")
            try:
                if SOLVER_REVIEWS_FILE.exists():
                    SOLVER_REVIEWS_FILE.unlink()
                    cleared_solver_reviews = True
            except Exception as e2:
                print(f"Error deleting {SOLVER_REVIEWS_FILE}: {e2}")

        # Also remove any lingering temporary solver reviews file
        temp_file = SOLVER_REVIEWS_FILE.with_suffix(".tmp")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

        deleted_files = 0
        if CONVERTED_DIR.exists():
            for f in CONVERTED_DIR.glob("*.txt"):
                try:
                    f.unlink()
                    deleted_files += 1
                except Exception as e:
                    print(f"Error deleting converted file {f}: {e}")

        return {
            "success": True,
            "cleared_count": count,
            "deleted_files": deleted_files,
            "cleared_solver_reviews": cleared_solver_reviews
        }

    def import_text(self, text: str, source_name: str = "Pasted") -> Dict[str, Any]:
        """Imports text from GG, Coin, 888, or generic format and converts to custom format."""
        from hand_replayer import parse_hands_from_text
        new_hands = parse_hands_from_text(text)

        if not new_hands:
            return {"success": False, "message": "Could not parse hand format. Supported sites: 888poker, CoinPoker, GGPoker."}

        # Convert and save each imported hand into the custom generic format
        existing_map = {h.hand_id: i for i, h in enumerate(self.hands)}
        for hand in new_hands:
            dest = CONVERTED_DIR / f"{hand.hand_id}.txt"
            dest.write_text(serialize_poker_hand(hand) + "\n", encoding="utf-8")
            if hand.hand_id in existing_map:
                self.hands[existing_map[hand.hand_id]] = hand
            else:
                existing_map[hand.hand_id] = len(self.hands)
                self.hands.append(hand)

        self.run_initial_analysis()
        return {"success": True, "count": len(new_hands), "hand_ids": [h.hand_id for h in new_hands]}
