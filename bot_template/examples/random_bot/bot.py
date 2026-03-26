#!/usr/bin/env python3

import json
import random
import sys


def choose_action(state: dict) -> dict:
    legal_actions = state["legal_actions"]
    choice = random.choice(legal_actions)
    response = {"action": choice["action"]}
    if "min_amount" in choice:
        response["amount"] = choice["min_amount"]
    return response


def main() -> int:
    state = json.load(sys.stdin)
    json.dump(choose_action(state), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
