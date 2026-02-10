#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/agent_worktree_finish.sh --base <branch> --title "<PR title>" --body "<PR body>" [--draft]

Example:
  scripts/agent_worktree_finish.sh --base marin --title "feat: implement M1 hand state" --body "Implements M1-T1 and tests."
USAGE
}

base="marin"
title=""
body=""
draft="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      base="${2:-}"
      shift 2
      ;;
    --title)
      title="${2:-}"
      shift 2
      ;;
    --body)
      body="${2:-}"
      shift 2
      ;;
    --draft)
      draft="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$title" || -z "$body" ]]; then
  echo "Error: --title and --body are required." >&2
  usage
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: run this command from inside a repository worktree." >&2
  exit 1
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$current_branch" == "main" || "$current_branch" == "$base" ]]; then
  echo "Error: refusing to open PR from protected/integration branch '$current_branch'." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree is dirty. Commit or stash changes first." >&2
  git status --short
  exit 1
fi

git push -u origin "$current_branch"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI ('gh') is required for automatic PR creation." >&2
  echo "Install it, run 'gh auth login', then re-run this command."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: GitHub CLI is not authenticated. Run 'gh auth login' and retry." >&2
  exit 1
fi

if gh pr view "$current_branch" >/dev/null 2>&1; then
  echo "PR already exists for branch '$current_branch'."
  gh pr view "$current_branch" --json url --jq '.url'
  exit 0
fi

pr_args=(--base "$base" --head "$current_branch" --title "$title" --body "$body")
if [[ "$draft" == "true" ]]; then
  pr_args+=(--draft)
fi

gh pr create "${pr_args[@]}"
