#!/usr/bin/env bash
#
# Convenience wrapper for scripts/read_roster.py so you don't have to type the
# full `uv run python ...` invocation.
#
# Usage:
#   ./scripts/read_roster.sh [league_name]     # default: kkupfl
#
# Runs from the project root (so `uv` and the .env are picked up) and forwards
# any arguments to the Python script.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$script_dir")"
cd "$project_root"

exec uv run python scripts/read_roster.py "$@"
