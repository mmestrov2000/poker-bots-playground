#!/usr/bin/env python3

import json
import sys


def choose_action(state: dict) -> dict:
    legal = {entry["action"]: entry for entry in state["legal_actions"]}
    big_blind = state["table"]["big_blind"]

    if "raise" in legal:
        minimum = legal["raise"]["min_amount"]
        maximum = legal["raise"]["max_amount"]
        target = min(maximum, max(minimum, big_blind * 4))
        return {"action": "raise", "amount": target}

    if "bet" in legal:
        minimum = legal["bet"]["min_amount"]
        maximum = legal["bet"]["max_amount"]
        target = min(maximum, max(minimum, big_blind * 3))
        return {"action": "bet", "amount": target}

    if "call" in legal:
        return {"action": "call"}

    if "check" in legal:
        return {"action": "check"}

    return {"action": "fold"}


def main() -> int:
    state = json.load(sys.stdin)
    json.dump(choose_action(state), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
