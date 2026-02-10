#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin="${PYTHON_BIN:-python3}"
venv_dir="$repo_root/backend/.venv"

"$python_bin" -m venv "$venv_dir"

# shellcheck source=/dev/null
source "$venv_dir/bin/activate"

pip install --upgrade pip
pip install -r "$repo_root/backend/requirements-dev.txt"

echo "Virtualenv ready at $venv_dir"
