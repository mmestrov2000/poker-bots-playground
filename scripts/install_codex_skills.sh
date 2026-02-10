#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/install_codex_skills.sh <owner>/<repo>"
  exit 1
fi

REPO="$1"

python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo "$REPO" \
  --path skills/main-agent \
  --path skills/feature-agent \
  --path skills/review-agent \
  --path skills/test-agent \
  --path skills/release-agent

echo "Skills installed. Restart Codex to pick up new skills."
