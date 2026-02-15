#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin="${PYTHON_BIN:-python3}"
venv_dir="$repo_root/backend/.venv"
venv_activate="$venv_dir/bin/activate"

"$python_bin" -m venv "$venv_dir"

# shellcheck source=/dev/null
source "$venv_activate"

pip install --upgrade pip
pip install -r "$repo_root/backend/requirements-dev.txt"

echo "Virtualenv ready at $venv_dir"

# A script cannot activate the parent shell when executed normally.
# If this file is sourced, keep the current shell activated.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "Activated current shell virtualenv: $venv_dir"
else
  echo "To activate in your current shell run:"
  echo "  source \"$venv_activate\""
fi
