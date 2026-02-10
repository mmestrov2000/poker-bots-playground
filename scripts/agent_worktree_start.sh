#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/agent_worktree_start.sh --agent <agent-name> --task <task-id> [--base <branch>] [--worktrees-dir <path>]

Example:
  scripts/agent_worktree_start.sh --agent feature-agent --task M1 --base marin
USAGE
}

agent=""
task=""
base="marin"
worktrees_dir=".worktrees"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="${2:-}"
      shift 2
      ;;
    --task)
      task="${2:-}"
      shift 2
      ;;
    --base)
      base="${2:-}"
      shift 2
      ;;
    --worktrees-dir)
      worktrees_dir="${2:-}"
      shift 2
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

if [[ -z "$agent" || -z "$task" ]]; then
  echo "Error: --agent and --task are required." >&2
  usage
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: run this command from inside the repository." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

agent_slug="$(slugify "$agent")"
task_slug="$(slugify "$task")"
branch="${base}-${agent_slug}-${task_slug}"
worktree_path="${worktrees_dir}/${branch}"

if ! git show-ref --verify --quiet "refs/heads/${base}"; then
  echo "Local base branch '${base}' not found. Attempting to fetch from origin..."
  git fetch origin "${base}:${base}"
fi

if git show-ref --verify --quiet "refs/heads/${branch}"; then
  echo "Error: branch '${branch}' already exists." >&2
  exit 1
fi

if [[ -e "$worktree_path" ]]; then
  echo "Error: worktree path already exists: $worktree_path" >&2
  exit 1
fi

mkdir -p "$worktrees_dir"

git worktree add "$worktree_path" -b "$branch" "$base"

echo "Created worktree: $worktree_path"
echo "Created branch:   $branch"
echo "Next:"
echo "  cd $worktree_path"
echo "  # implement task, commit changes"
echo "  scripts/agent_worktree_finish.sh --base $base --title \"<PR title>\" --body \"<PR summary>\""
