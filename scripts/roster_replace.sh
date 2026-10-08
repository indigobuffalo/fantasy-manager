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
unset ADD_ID
unset DROP_ID
unset LEAGUE

# set defaults for optional args
START_OPT=""
FAAB_OPT=""
WAIVERS="false"

while getopts "a:d:f:hl:s:w" opt; do
  case $opt in
    a) # The id of the player to be added.
      ADD_ID="$OPTARG"
      ;;
    d) # The id of the player to be dropped.
      DROP_ID="$OPTARG"
      ;;
    f) # faab to bid on the waiver claim
      FAAB_OPT="--faab $OPTARG"
      ;;
    h) # Display help text.
      usage
      exit 0
      ;;
    l) # The league name.
      LEAGUE="$OPTARG"
      ;;
    s) # ISO 8601 time stamp which sets the time to add the player.
      START_OPT="--start $OPTARG"
      ;;
    w) # Whether the player to add is on waivers.
      WAIVERS="true"
      ;;
    ?) # Display help.
      usage
      exit 1
      ;;
  esac
done

check_args(){
  [ "${LEAGUE}x" == "x" ] && echo -e "ERROR: Must specify league!\n" && usage && exit 1
  [ "${ADD_ID}x" == "x" ] && echo -e "ERROR: Must specify id of player to add!\n" && usage && exit 1
  [ "${DROP_ID}x" == "x" ] && echo -e "ERROR: Must specify id of player to drop!\n" && usage && exit 1
  [ "$NOW" == "true" ] && [ -n "$START_OPT" ] && echo -e "ERROR: Cannot use --now together with -s!\n" && usage && exit 1
}
check_args

[ "$NOW" == "true" ] && START_OPT="--start now"

if [[ "$WAIVERS" == "true" ]]; then
    caffeinate -is fmgr roster replace claim --league $LEAGUE --add $ADD_ID --drop $DROP_ID $FAAB_OPT $START_OPT
else
    caffeinate -is fmgr roster replace --league $LEAGUE --add $ADD_ID --drop $DROP_ID $START_OPT
fi
