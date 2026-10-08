#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0 && echo "--now) # Shortcut for '-s now' (execute immediately)."; exit 0; }
[ $# -eq 0 ] && usage

# Translate the convenience flag `--now` into `-s now` and strip it from the
# args before getopts (which only understands short options) sees it.
NOW="false"
args=()
for arg in "$@"; do
  case "$arg" in
    --now) NOW="true" ;;
    *) args+=("$arg") ;;
  esac
done
set -- "${args[@]}"

# unset required args
unset LEAGUE
unset DATE

# set defaults for optional args
START=""
LINEUP_FILE=""
LINEUP_JSON=""

while getopts "d:f:hj:l:s:" opt; do
  case $opt in
    d) # The date (YYYY-MM-DD) whose lineup to set.
      DATE="$OPTARG"
      ;;
    f) # Path to a JSON file of {player_id, position} changes.
      LINEUP_FILE="$OPTARG"
      ;;
    h) # Display help text.
      usage
      exit 0
      ;;
    j) # Inline JSON string of {player_id, position} changes (quote it).
      LINEUP_JSON="$OPTARG"
      ;;
    l) # The league name.
      LEAGUE="$OPTARG"
      ;;
    s) # ISO 8601 timestamp for when to set the lineup.
      START="$OPTARG"
      ;;
    ?) # Display help.
      usage
      exit 1
      ;;
  esac
done

check_args(){
  [ "${LEAGUE}x" == "x" ] && echo -e "ERROR: Must specify league!\n" && usage && exit 1
  [ "${DATE}x" == "x" ] && echo -e "ERROR: Must specify lineup date (-d)!\n" && usage && exit 1
  [ -z "$LINEUP_FILE" ] && [ -z "$LINEUP_JSON" ] && echo -e "ERROR: Must specify -f <file> or -j <json>!\n" && usage && exit 1
  [ -n "$LINEUP_FILE" ] && [ -n "$LINEUP_JSON" ] && echo -e "ERROR: Cannot use -f and -j together!\n" && usage && exit 1
  [ "$NOW" == "true" ] && [ -n "$START" ] && echo -e "ERROR: Cannot use --now together with -s!\n" && usage && exit 1
}
check_args

[ "$NOW" == "true" ] && START="now"

# Build the argv as an array so a -j JSON string with spaces stays a single arg.
CMD_ARGS=(lineup set --league "$LEAGUE" --date "$DATE")
[ -n "$LINEUP_FILE" ] && CMD_ARGS+=(--lineup-file "$LINEUP_FILE")
[ -n "$LINEUP_JSON" ] && CMD_ARGS+=(--lineup-json "$LINEUP_JSON")
[ -n "$START" ] && CMD_ARGS+=(--start "$START")

caffeinate -is fmgr "${CMD_ARGS[@]}"
