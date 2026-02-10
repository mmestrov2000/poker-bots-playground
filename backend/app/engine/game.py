from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from random import Random, SystemRandom
from typing import Iterable, Literal

from app.bots.runtime import BotRunner


SeatId = Literal["A", "B"]


RANK_TO_CHAR = {
    14: "A",
    13: "K",
    12: "Q",
    11: "J",
    10: "T",
    9: "9",
    8: "8",
    7: "7",
    6: "6",
    5: "5",
    4: "4",
    3: "3",
    2: "2",
}

CHAR_TO_RANK = {value: key for key, value in RANK_TO_CHAR.items()}
SUITS = ("s", "h", "d", "c")


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __str__(self) -> str:
        return f"{RANK_TO_CHAR[self.rank]}{self.suit}"


@dataclass
class ActionEvent:
    seat: SeatId
    action: str
    amount: int
    street: str


@dataclass
class HandResult:
    winner: SeatId
    pot_cents: int
    board: list[Card]
    hole_cards: dict[SeatId, list[Card]]
    actions: list[ActionEvent]


class PokerEngine:
    def __init__(
        self,
        *,
        rng: Random | None = None,
        starting_stack_cents: int = 10000,
        small_blind_cents: int = 50,
        big_blind_cents: int = 100,
    ) -> None:
        self.rng = rng or SystemRandom()
        self.starting_stack_cents = starting_stack_cents
        self.small_blind_cents = small_blind_cents
        self.big_blind_cents = big_blind_cents

    def play_hand(
        self,
        *,
        hand_id: str,
        bot_a: BotRunner,
        bot_b: BotRunner,
        seat_a_name: str,
        seat_b_name: str,
    ) -> HandResult:
        deck = self._build_deck()
        self.rng.shuffle(deck)

        button = self._button_for_hand(hand_id)
        small_blind_seat = button
        big_blind_seat = self._other_seat(button)

        stacks = {"A": self.starting_stack_cents, "B": self.starting_stack_cents}
        bets = {"A": 0, "B": 0}
        pot = 0
        actions: list[ActionEvent] = []

        hole_cards = {
            "A": [deck.pop(), deck.pop()],
            "B": [deck.pop(), deck.pop()],
        }
        board: list[Card] = []

        pot += self._post_blind(stacks, bets, small_blind_seat, self.small_blind_cents, actions)
        pot += self._post_blind(stacks, bets, big_blind_seat, self.big_blind_cents, actions)

        current_bet = bets[big_blind_seat]
        min_raise = self.big_blind_cents
        last_raise_seat: SeatId | None = big_blind_seat
        acted_since_raise: set[SeatId] = {big_blind_seat}

        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="preflop",
            starting_seat=small_blind_seat,
            bots={"A": bot_a, "B": bot_b},
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            last_raise_ref=[last_raise_seat],
            acted_since_raise_ref=[acted_since_raise],
            actions=actions,
            seat_names={"A": seat_a_name, "B": seat_b_name},
        )
        pot = pot_ref[0]
        if folded_winner:
            return HandResult(
                winner=folded_winner,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
            )

        bets = {"A": 0, "B": 0}
        current_bet = 0
        min_raise = self.big_blind_cents
        last_raise_seat = None
        acted_since_raise = set()

        board.extend([deck.pop(), deck.pop(), deck.pop()])
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="flop",
            starting_seat=big_blind_seat,
            bots={"A": bot_a, "B": bot_b},
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            last_raise_ref=[last_raise_seat],
            acted_since_raise_ref=[acted_since_raise],
            actions=actions,
            seat_names={"A": seat_a_name, "B": seat_b_name},
        )
        pot = pot_ref[0]
        if folded_winner:
            return HandResult(
                winner=folded_winner,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
            )

        bets = {"A": 0, "B": 0}
        current_bet = 0
        min_raise = self.big_blind_cents
        last_raise_seat = None
        acted_since_raise = set()

        board.append(deck.pop())
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="turn",
            starting_seat=big_blind_seat,
            bots={"A": bot_a, "B": bot_b},
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            last_raise_ref=[last_raise_seat],
            acted_since_raise_ref=[acted_since_raise],
            actions=actions,
            seat_names={"A": seat_a_name, "B": seat_b_name},
        )
        pot = pot_ref[0]
        if folded_winner:
            return HandResult(
                winner=folded_winner,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
            )

        bets = {"A": 0, "B": 0}
        current_bet = 0
        min_raise = self.big_blind_cents
        last_raise_seat = None
        acted_since_raise = set()

        board.append(deck.pop())
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="river",
            starting_seat=big_blind_seat,
            bots={"A": bot_a, "B": bot_b},
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            last_raise_ref=[last_raise_seat],
            acted_since_raise_ref=[acted_since_raise],
            actions=actions,
            seat_names={"A": seat_a_name, "B": seat_b_name},
        )
        pot = pot_ref[0]
        if folded_winner:
            return HandResult(
                winner=folded_winner,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
            )

        winner = self._determine_showdown_winner(hole_cards, board)
        return HandResult(
            winner=winner,
            pot_cents=pot,
            board=board,
            hole_cards=hole_cards,
            actions=actions,
        )

    def _build_deck(self) -> list[Card]:
        return [Card(rank=rank, suit=suit) for rank in range(2, 15) for suit in SUITS]

    def _button_for_hand(self, hand_id: str) -> SeatId:
        try:
            numeric_id = int(hand_id)
        except ValueError:
            numeric_id = 1
        return "A" if numeric_id % 2 == 1 else "B"

    def button_for_hand(self, hand_id: str) -> SeatId:
        return self._button_for_hand(hand_id)

    def _other_seat(self, seat: SeatId) -> SeatId:
        return "B" if seat == "A" else "A"

    def _post_blind(
        self,
        stacks: dict[SeatId, int],
        bets: dict[SeatId, int],
        seat: SeatId,
        amount: int,
        actions: list[ActionEvent],
    ) -> int:
        actual = min(amount, stacks[seat])
        stacks[seat] -= actual
        bets[seat] += actual
        actions.append(ActionEvent(seat=seat, action="blind", amount=actual, street="preflop"))
        return actual

    def _run_betting_round(
        self,
        *,
        street: str,
        starting_seat: SeatId,
        bots: dict[SeatId, BotRunner],
        stacks: dict[SeatId, int],
        bets: dict[SeatId, int],
        board: list[Card],
        hole_cards: dict[SeatId, list[Card]],
        pot_ref: list[int],
        current_bet_ref: list[int],
        min_raise_ref: list[int],
        last_raise_ref: list[SeatId | None],
        acted_since_raise_ref: list[set[SeatId]],
        actions: list[ActionEvent],
        seat_names: dict[SeatId, str],
    ) -> SeatId | None:
        seat = starting_seat
        while True:
            to_call = current_bet_ref[0] - bets[seat]
            legal = legal_actions(to_call=to_call, stack=stacks[seat], current_bet=current_bet_ref[0])
            state = build_bot_state(
                seat=seat,
                street=street,
                hole_cards=hole_cards[seat],
                board=board,
                pot=pot_ref[0],
                stack=stacks[seat],
                to_call=to_call,
                min_raise_to=min_raise_to(current_bet_ref[0], min_raise_ref[0]),
                legal_actions=legal,
                seat_name=seat_names[seat],
            )
            raw_action = bots[seat].act(state)
            action, amount = normalize_action(
                raw_action,
                to_call=to_call,
                current_bet=current_bet_ref[0],
                min_raise_to=min_raise_to(current_bet_ref[0], min_raise_ref[0]),
                stack=stacks[seat],
                bet=bets[seat],
                legal_actions=legal,
            )

            if action == "fold":
                actions.append(ActionEvent(seat=seat, action="fold", amount=0, street=street))
                return self._other_seat(seat)

            if action == "check":
                actions.append(ActionEvent(seat=seat, action="check", amount=0, street=street))
            elif action == "call":
                delta = min(amount, stacks[seat])
                stacks[seat] -= delta
                bets[seat] += delta
                pot_ref[0] += delta
                actions.append(ActionEvent(seat=seat, action="call", amount=delta, street=street))
            elif action in {"bet", "raise"}:
                desired_total = amount
                delta = max(desired_total - bets[seat], 0)
                delta = min(delta, stacks[seat])
                stacks[seat] -= delta
                bets[seat] += delta
                pot_ref[0] += delta
                raise_size = bets[seat] - current_bet_ref[0]
                current_bet_ref[0] = bets[seat]
                min_raise_ref[0] = max(raise_size, min_raise_ref[0])
                last_raise_ref[0] = seat
                acted_since_raise_ref[0] = {seat}
                actions.append(ActionEvent(seat=seat, action=action, amount=delta, street=street))

            if action in {"check", "call"}:
                acted_since_raise_ref[0].add(seat)

            if bets["A"] == bets["B"]:
                if last_raise_ref[0] is None:
                    if acted_since_raise_ref[0] == {"A", "B"}:
                        return None
                else:
                    if acted_since_raise_ref[0] == {"A", "B"}:
                        return None

            seat = self._other_seat(seat)

    def _determine_showdown_winner(
        self, hole_cards: dict[SeatId, list[Card]], board: list[Card]
    ) -> SeatId:
        rank_a = evaluate_best_hand(hole_cards["A"] + board)
        rank_b = evaluate_best_hand(hole_cards["B"] + board)
        if rank_a > rank_b:
            return "A"
        if rank_b > rank_a:
            return "B"
        return "A"


def legal_actions(*, to_call: int, stack: int, current_bet: int) -> list[str]:
    actions: list[str] = []
    if to_call > 0:
        actions.append("fold")
        actions.append("call")
        if stack > to_call:
            actions.append("raise")
    else:
        actions.append("check")
        if stack > 0:
            actions.append("bet")
    return actions


def min_raise_to(current_bet: int, min_raise: int) -> int:
    if current_bet == 0:
        return min_raise
    return current_bet + min_raise


def normalize_action(
    raw_action: dict | None,
    *,
    to_call: int,
    current_bet: int,
    min_raise_to: int,
    stack: int,
    bet: int,
    legal_actions: Iterable[str],
) -> tuple[str, int]:
    if not isinstance(raw_action, dict):
        return _fallback_action(to_call)

    action = raw_action.get("action")
    amount = raw_action.get("amount", 0)

    if action not in {"fold", "check", "call", "bet", "raise"}:
        return _fallback_action(to_call)

    if action == "bet" and current_bet > 0:
        action = "raise"
    elif action == "raise" and current_bet == 0:
        action = "bet"
    elif action == "check" and to_call > 0:
        action = "call"
    elif action == "call" and to_call <= 0:
        action = "check"

    if action not in set(legal_actions):
        return _fallback_action(to_call)

    if action == "fold":
        if to_call == 0:
            return "check", 0
        return "fold", 0

    if action == "check":
        return "check", 0

    if action == "call":
        return "call", min(to_call, stack)

    if action in {"bet", "raise"}:
        max_total = bet + stack
        if max_total <= current_bet:
            if to_call > 0:
                return "call", min(to_call, stack)
            return "check", 0

        try:
            desired_total = int(amount)
        except (TypeError, ValueError):
            desired_total = min_raise_to

        if desired_total < min_raise_to:
            desired_total = min_raise_to if max_total >= min_raise_to else max_total
        if desired_total > max_total:
            desired_total = max_total
        if desired_total <= current_bet:
            if to_call > 0:
                return "call", min(to_call, stack)
            return "check", 0
        return action, desired_total

    return _fallback_action(to_call)


def _fallback_action(to_call: int) -> tuple[str, int]:
    if to_call > 0:
        return "fold", 0
    return "check", 0


def evaluate_best_hand(cards: list[Card]) -> tuple:
    best: tuple | None = None
    for combo in combinations(cards, 5):
        rank = evaluate_five_card_hand(combo)
        if best is None or rank > best:
            best = rank
    return best or (0, [])


def evaluate_five_card_hand(cards: Iterable[Card]) -> tuple:
    ranks = sorted((card.rank for card in cards), reverse=True)
    suits = [card.suit for card in cards]
    flush = len(set(suits)) == 1

    unique_ranks = sorted(set(ranks), reverse=True)
    straight = False
    straight_high = None
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[-1] == 4:
            straight = True
            straight_high = unique_ranks[0]
        elif unique_ranks == [14, 5, 4, 3, 2]:
            straight = True
            straight_high = 5

    counts: dict[int, int] = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    count_sorted = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    count_values = [count for _, count in count_sorted]
    ordered_ranks = [rank for rank, _ in count_sorted]

    if straight and flush:
        return (8, [straight_high])
    if count_values == [4, 1]:
        return (7, [ordered_ranks[0], ordered_ranks[1]])
    if count_values == [3, 2]:
        return (6, [ordered_ranks[0], ordered_ranks[1]])
    if flush:
        return (5, ranks)
    if straight:
        return (4, [straight_high])
    if count_values == [3, 1, 1]:
        kickers = sorted([rank for rank, count in counts.items() if count == 1], reverse=True)
        return (3, [ordered_ranks[0]] + kickers)
    if count_values == [2, 2, 1]:
        pair_ranks = sorted([rank for rank, count in counts.items() if count == 2], reverse=True)
        kicker = [rank for rank, count in counts.items() if count == 1][0]
        return (2, pair_ranks + [kicker])
    if count_values == [2, 1, 1, 1]:
        kickers = sorted([rank for rank, count in counts.items() if count == 1], reverse=True)
        return (1, [ordered_ranks[0]] + kickers)
    return (0, ranks)


def build_bot_state(
    *,
    seat: SeatId,
    street: str,
    hole_cards: list[Card],
    board: list[Card],
    pot: int,
    stack: int,
    to_call: int,
    min_raise_to: int,
    legal_actions: list[str],
    seat_name: str,
) -> dict:
    return {
        "seat": seat,
        "seat_name": seat_name,
        "street": street,
        "hole_cards": [str(card) for card in hole_cards],
        "board": [str(card) for card in board],
        "pot": pot,
        "stack": stack,
        "to_call": to_call,
        "min_raise_to": min_raise_to,
        "legal_actions": legal_actions,
    }
