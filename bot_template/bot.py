#!/usr/bin/env python3

import json
import sys


def build_opponent_stats(state: dict) -> dict[str, dict[str, int]]:
    hero_id = state["hero"]["player_id"]
    stats: dict[str, dict[str, int]] = {}
    for event in state["action_history"]:
        player_id = event["player_id"]
        if player_id == hero_id:
            continue
        player_stats = stats.setdefault(player_id, {"actions": 0, "aggressive_actions": 0})
        player_stats["actions"] += 1
        if event["action"] in {"bet", "raise"}:
            player_stats["aggressive_actions"] += 1
    return stats


def choose_action(state: dict) -> dict:
    hero = state["hero"]
    to_call = hero["to_call"]
    pot = state["board"]["pot"]
    legal = {entry["action"]: entry for entry in state["legal_actions"]}

    opponent_stats = build_opponent_stats(state)
    aggressive_opponents = sum(
        1
        for values in opponent_stats.values()
        if values["aggressive_actions"] * 2 >= values["actions"] and values["actions"] > 0
    )

    if "check" in legal:
        return {"action": "check"}

    if "call" in legal and aggressive_opponents == 0 and to_call <= pot // 4:
        return {"action": "call"}

    if "fold" in legal:
        return {"action": "fold"}

    first = next(iter(legal.values()))
    response = {"action": first["action"]}
    if "min_amount" in first:
        response["amount"] = first["min_amount"]
    return response


def main() -> int:
    state = json.load(sys.stdin)
    response = choose_action(state)
    json.dump(response, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
