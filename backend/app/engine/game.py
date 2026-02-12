from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from random import Random, SystemRandom
from typing import Iterable, Literal

from app.bots.runtime import BotRunner


SeatId = Literal["1", "2", "3", "4", "5", "6"]
SEAT_ORDER = ("1", "2", "3", "4", "5", "6")
SEAT_INDEX = {seat: index for index, seat in enumerate(SEAT_ORDER)}


def order_seats(seats: Iterable[SeatId]) -> list[SeatId]:
    return sorted(seats, key=lambda seat: SEAT_INDEX[seat])


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
    winners: list[SeatId]
    pot_cents: int
    board: list[Card]
    hole_cards: dict[SeatId, list[Card]]
    actions: list[ActionEvent]
    deltas: dict[SeatId, int]
    active_seats: list[SeatId]


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
        bots: dict[SeatId, BotRunner],
        seat_names: dict[SeatId, str],
        button: SeatId,
    ) -> HandResult:
        active_seats = order_seats(bots.keys())
        if len(active_seats) < 2:
            raise RuntimeError("At least two seats must be active to play a hand")
        if button not in active_seats:
            button = active_seats[0]
        deck = self._build_deck()
        self.rng.shuffle(deck)

        (
            small_blind_seat,
            big_blind_seat,
            preflop_start,
            postflop_start,
        ) = self._blind_positions(active_seats, button)

        stacks = {seat: self.starting_stack_cents for seat in active_seats}
        bets = {seat: 0 for seat in active_seats}
        contributions = {seat: 0 for seat in active_seats}
        pot = 0
        actions: list[ActionEvent] = []

        hole_cards = {seat: [deck.pop(), deck.pop()] for seat in active_seats}
        board: list[Card] = []
        folded: set[SeatId] = set()

        pot += self._post_blind(
            stacks,
            bets,
            contributions,
            small_blind_seat,
            self.small_blind_cents,
            actions,
        )
        pot += self._post_blind(
            stacks,
            bets,
            contributions,
            big_blind_seat,
            self.big_blind_cents,
            actions,
        )

        current_bet = bets[big_blind_seat]
        min_raise = self.big_blind_cents

        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="preflop",
            starting_seat=preflop_start,
            order=active_seats,
            bots=bots,
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            actions=actions,
            seat_names=seat_names,
            folded=folded,
            contributions=contributions,
            button=button,
            small_blind=small_blind_seat,
            big_blind=big_blind_seat,
        )
        pot = pot_ref[0]
        if folded_winner:
            winners, deltas = self._finalize_folded_hand(
                winner=folded_winner,
                contributions=contributions,
                active_seats=active_seats,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        if self._no_actionable_seats(active_seats, folded, stacks):
            self._deal_remaining_board(deck, board)
            winners, deltas = self._resolve_showdown(
                active_seats=active_seats,
                folded=folded,
                hole_cards=hole_cards,
                board=board,
                contributions=contributions,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        self._reset_bets(bets)
        current_bet = 0
        min_raise = self.big_blind_cents

        board.extend([deck.pop(), deck.pop(), deck.pop()])
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="flop",
            starting_seat=postflop_start,
            order=active_seats,
            bots=bots,
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            actions=actions,
            seat_names=seat_names,
            folded=folded,
            contributions=contributions,
            button=button,
            small_blind=small_blind_seat,
            big_blind=big_blind_seat,
        )
        pot = pot_ref[0]
        if folded_winner:
            winners, deltas = self._finalize_folded_hand(
                winner=folded_winner,
                contributions=contributions,
                active_seats=active_seats,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        if self._no_actionable_seats(active_seats, folded, stacks):
            self._deal_remaining_board(deck, board)
            winners, deltas = self._resolve_showdown(
                active_seats=active_seats,
                folded=folded,
                hole_cards=hole_cards,
                board=board,
                contributions=contributions,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        self._reset_bets(bets)
        current_bet = 0
        min_raise = self.big_blind_cents

        board.append(deck.pop())
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="turn",
            starting_seat=postflop_start,
            order=active_seats,
            bots=bots,
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            actions=actions,
            seat_names=seat_names,
            folded=folded,
            contributions=contributions,
            button=button,
            small_blind=small_blind_seat,
            big_blind=big_blind_seat,
        )
        pot = pot_ref[0]
        if folded_winner:
            winners, deltas = self._finalize_folded_hand(
                winner=folded_winner,
                contributions=contributions,
                active_seats=active_seats,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        if self._no_actionable_seats(active_seats, folded, stacks):
            self._deal_remaining_board(deck, board)
            winners, deltas = self._resolve_showdown(
                active_seats=active_seats,
                folded=folded,
                hole_cards=hole_cards,
                board=board,
                contributions=contributions,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        self._reset_bets(bets)
        current_bet = 0
        min_raise = self.big_blind_cents

        board.append(deck.pop())
        pot_ref = [pot]
        folded_winner = self._run_betting_round(
            street="river",
            starting_seat=postflop_start,
            order=active_seats,
            bots=bots,
            stacks=stacks,
            bets=bets,
            board=board,
            hole_cards=hole_cards,
            pot_ref=pot_ref,
            current_bet_ref=[current_bet],
            min_raise_ref=[min_raise],
            actions=actions,
            seat_names=seat_names,
            folded=folded,
            contributions=contributions,
            button=button,
            small_blind=small_blind_seat,
            big_blind=big_blind_seat,
        )
        pot = pot_ref[0]
        if folded_winner:
            winners, deltas = self._finalize_folded_hand(
                winner=folded_winner,
                contributions=contributions,
                active_seats=active_seats,
            )
            return HandResult(
                winners=winners,
                pot_cents=pot,
                board=board,
                hole_cards=hole_cards,
                actions=actions,
                deltas=deltas,
                active_seats=active_seats,
            )

        winners, deltas = self._resolve_showdown(
            active_seats=active_seats,
            folded=folded,
            hole_cards=hole_cards,
            board=board,
            contributions=contributions,
        )
        return HandResult(
            winners=winners,
            pot_cents=pot,
            board=board,
            hole_cards=hole_cards,
            actions=actions,
            deltas=deltas,
            active_seats=active_seats,
        )

    def _build_deck(self) -> list[Card]:
        return [Card(rank=rank, suit=suit) for rank in range(2, 15) for suit in SUITS]

    def button_for_hand(self, hand_id: str, seats: Iterable[SeatId] = SEAT_ORDER) -> SeatId:
        ordered = order_seats(seats)
        try:
            numeric_id = int(hand_id)
        except ValueError:
            numeric_id = 1
        return ordered[(numeric_id - 1) % len(ordered)]

    def _post_blind(
        self,
        stacks: dict[SeatId, int],
        bets: dict[SeatId, int],
        contributions: dict[SeatId, int],
        seat: SeatId,
        amount: int,
        actions: list[ActionEvent],
    ) -> int:
        actual = min(amount, stacks[seat])
        stacks[seat] -= actual
        bets[seat] += actual
        contributions[seat] += actual
        actions.append(ActionEvent(seat=seat, action="blind", amount=actual, street="preflop"))
        return actual

    def _run_betting_round(
        self,
        *,
        street: str,
        starting_seat: SeatId,
        order: list[SeatId],
        bots: dict[SeatId, BotRunner],
        stacks: dict[SeatId, int],
        bets: dict[SeatId, int],
        board: list[Card],
        hole_cards: dict[SeatId, list[Card]],
        pot_ref: list[int],
        current_bet_ref: list[int],
        min_raise_ref: list[int],
        actions: list[ActionEvent],
        seat_names: dict[SeatId, str],
        folded: set[SeatId],
        contributions: dict[SeatId, int],
        button: SeatId,
        small_blind: SeatId,
        big_blind: SeatId,
    ) -> SeatId | None:
        active = {seat for seat in order if seat not in folded}
        pending = {seat for seat in active if stacks[seat] > 0}
        if not pending:
            return None

        seat = starting_seat if starting_seat in pending else _next_pending_seat(
            starting_seat, order, pending
        )
        while pending and seat is not None:
            if seat not in pending:
                seat = _next_pending_seat(seat, order, pending)
                continue

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
                seats=order,
                seat_names=seat_names,
                stacks=stacks,
                bets=bets,
                folded=folded,
                button=button,
                small_blind=small_blind,
                big_blind=big_blind,
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
                folded.add(seat)
                pending.discard(seat)
                active = {seat for seat in order if seat not in folded}
                if len(active) == 1:
                    return next(iter(active))
                seat = _next_pending_seat(seat, order, pending)
                continue

            if action == "check":
                actions.append(ActionEvent(seat=seat, action="check", amount=0, street=street))
                pending.discard(seat)
            elif action == "call":
                delta = min(amount, stacks[seat])
                stacks[seat] -= delta
                bets[seat] += delta
                contributions[seat] += delta
                pot_ref[0] += delta
                actions.append(ActionEvent(seat=seat, action="call", amount=delta, street=street))
                pending.discard(seat)
            elif action in {"bet", "raise"}:
                desired_total = amount
                delta = max(desired_total - bets[seat], 0)
                delta = min(delta, stacks[seat])
                stacks[seat] -= delta
                bets[seat] += delta
                contributions[seat] += delta
                pot_ref[0] += delta
                raise_size = bets[seat] - current_bet_ref[0]
                current_bet_ref[0] = bets[seat]
                if raise_size > 0:
                    min_raise_ref[0] = max(raise_size, min_raise_ref[0])
                pending = {pending_seat for pending_seat in active if stacks[pending_seat] > 0}
                pending.discard(seat)
                actions.append(ActionEvent(seat=seat, action=action, amount=delta, street=street))

            if not pending:
                return None

            seat = _next_pending_seat(seat, order, pending)

    def _blind_positions(
        self, active_seats: list[SeatId], button: SeatId
    ) -> tuple[SeatId, SeatId, SeatId, SeatId]:
        ordered = active_seats
        button_index = ordered.index(button)
        if len(ordered) == 2:
            small_blind = button
            big_blind = ordered[(button_index + 1) % 2]
            preflop_start = small_blind
            postflop_start = big_blind
        else:
            small_blind = ordered[(button_index + 1) % len(ordered)]
            big_blind = ordered[(button_index + 2) % len(ordered)]
            preflop_start = ordered[(button_index + 3) % len(ordered)]
            postflop_start = ordered[(button_index + 1) % len(ordered)]
        return small_blind, big_blind, preflop_start, postflop_start

    def _reset_bets(self, bets: dict[SeatId, int]) -> None:
        for seat in bets:
            bets[seat] = 0

    def _no_actionable_seats(
        self,
        active_seats: list[SeatId],
        folded: set[SeatId],
        stacks: dict[SeatId, int],
    ) -> bool:
        for seat in active_seats:
            if seat in folded:
                continue
            if stacks[seat] > 0:
                return False
        return True

    def _deal_remaining_board(self, deck: list[Card], board: list[Card]) -> None:
        while len(board) < 5 and deck:
            board.append(deck.pop())

    def _finalize_folded_hand(
        self,
        *,
        winner: SeatId,
        contributions: dict[SeatId, int],
        active_seats: list[SeatId],
    ) -> tuple[list[SeatId], dict[SeatId, int]]:
        payouts = {seat: 0 for seat in active_seats}
        payouts[winner] = sum(contributions.values())
        deltas = {seat: payouts[seat] - contributions[seat] for seat in active_seats}
        return [winner], deltas

    def _resolve_showdown(
        self,
        *,
        active_seats: list[SeatId],
        folded: set[SeatId],
        hole_cards: dict[SeatId, list[Card]],
        board: list[Card],
        contributions: dict[SeatId, int],
    ) -> tuple[list[SeatId], dict[SeatId, int]]:
        showdown_seats = [seat for seat in active_seats if seat not in folded]
        ranks = {seat: evaluate_best_hand(hole_cards[seat] + board) for seat in showdown_seats}
        best_rank = max(ranks.values())
        winners = [seat for seat, rank in ranks.items() if rank == best_rank]
        payouts = self._calculate_payouts(
            contributions=contributions, ranks=ranks, order=active_seats
        )
        deltas = {seat: payouts.get(seat, 0) - contributions[seat] for seat in active_seats}
        return winners, deltas

    def _calculate_payouts(
        self,
        *,
        contributions: dict[SeatId, int],
        ranks: dict[SeatId, tuple],
        order: list[SeatId],
    ) -> dict[SeatId, int]:
        payouts = {seat: 0 for seat in contributions}
        levels = sorted({amount for amount in contributions.values() if amount > 0})
        previous = 0
        for level in levels:
            if level <= previous:
                continue
            involved = [seat for seat, amount in contributions.items() if amount >= level]
            if not involved:
                previous = level
                continue
            slice_amount = (level - previous) * len(involved)
            eligible = [seat for seat in involved if seat in ranks]
            if not eligible:
                previous = level
                continue
            best_rank = max(ranks[seat] for seat in eligible)
            winners = [seat for seat in eligible if ranks[seat] == best_rank]
            payout_each = slice_amount // len(winners)
            remainder = slice_amount % len(winners)
            for seat in winners:
                payouts[seat] += payout_each
            if remainder:
                winners_ordered = sorted(winners, key=lambda seat: order.index(seat))
                for idx in range(remainder):
                    payouts[winners_ordered[idx % len(winners_ordered)]] += 1
            previous = level
        return payouts


def _next_pending_seat(
    current_seat: SeatId, order: list[SeatId], pending: set[SeatId]
) -> SeatId | None:
    if not pending:
        return None
    try:
        start_index = order.index(current_seat)
    except ValueError:
        start_index = -1
    for offset in range(1, len(order) + 1):
        seat = order[(start_index + offset) % len(order)]
        if seat in pending:
            return seat
    return None


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
    seats: list[SeatId],
    seat_names: dict[SeatId, str],
    stacks: dict[SeatId, int],
    bets: dict[SeatId, int],
    folded: set[SeatId],
    button: SeatId,
    small_blind: SeatId,
    big_blind: SeatId,
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
        "players": [
            {
                "seat": seat_id,
                "name": seat_names[seat_id],
                "stack": stacks[seat_id],
                "bet": bets[seat_id],
                "folded": seat_id in folded,
                "all_in": stacks[seat_id] == 0,
            }
            for seat_id in seats
        ],
        "button": button,
        "small_blind": small_blind,
        "big_blind": big_blind,
    }
