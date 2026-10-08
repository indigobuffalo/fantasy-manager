#!/usr/bin/env bash
#
# Thin shim kept for muscle memory: forwards to the first-class
# `fmgr roster read` command. Maps the optional positional [league_name]
# (default: kkupfl) onto the command's --league flag.
#
# Usage:
#   ./scripts/read_roster.sh [league_name]     # default: kkupfl
set -euo pipefail

exec fmgr roster read --league "${1:-kkupfl}"
