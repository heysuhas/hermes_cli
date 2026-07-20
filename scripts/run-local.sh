#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SR_HOME="${SR_HOME:-$HOME/.sr}"
RUNTIME_ROOT="$SR_HOME/sr-agent"
VENV_ROOT="$RUNTIME_ROOT/venv"
VENV_PYTHON="$VENV_ROOT/bin/python"
MANAGED_UV="$SR_HOME/bin/uv"

mkdir -p "$RUNTIME_ROOT"

if [[ ! -x "$MANAGED_UV" ]]; then
  bash "$REPO_ROOT/scripts/install.sh" \
    --stage prerequisites \
    --sr-home "$SR_HOME" \
    --non-interactive
fi

if [[ ! -x "$MANAGED_UV" ]]; then
  echo "SR could not install uv at $MANAGED_UV." >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  "$MANAGED_UV" venv "$VENV_ROOT" --python 3.11
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "SR could not create the managed Python environment at $VENV_ROOT." >&2
  exit 1
fi

export UV_PROJECT_ENVIRONMENT="$VENV_ROOT"
"$MANAGED_UV" sync --project "$REPO_ROOT" --extra all --extra dev --locked
# Migrate environments created by older checkout instructions. Do this only
# after the shared environment is healthy, so a failed setup never destroys the
# user's only working environment.
for legacy_venv in "$REPO_ROOT/.venv" "$REPO_ROOT/venv"; do
  if [[ -d "$legacy_venv" && "$legacy_venv" != "$VENV_ROOT" ]]; then
    rm -rf "$legacy_venv"
  fi
done

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV_PYTHON" -m sr_cli.main "$@"
