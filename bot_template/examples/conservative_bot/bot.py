#!/usr/bin/env python3

import json
import sys


def choose_action(state: dict) -> dict:
    legal = {entry["action"]: entry for entry in state["legal_actions"]}
    to_call = state["hero"]["to_call"]
    big_blind = state["table"]["big_blind"]

    if "check" in legal:
        return {"action": "check"}

    if "call" in legal and to_call <= big_blind:
        return {"action": "call"}

    if "fold" in legal:
        return {"action": "fold"}

    if "call" in legal:
        return {"action": "call"}

    if "bet" in legal:
        return {"action": "bet", "amount": legal["bet"]["min_amount"]}

    first = next(iter(legal.values()))
    response = {"action": first["action"]}
    if "min_amount" in first:
        response["amount"] = first["min_amount"]
    return response


def main() -> int:
    state = json.load(sys.stdin)
    json.dump(choose_action(state), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
