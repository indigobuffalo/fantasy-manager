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
unset DROP_ID
unset LEAGUE

# set defaults for optional args
START_OPT=""

while getopts "d:hl:s:" opt; do
  case $opt in
    d) # The id of the player to be dropped.
      DROP_ID="$OPTARG"
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
    ?) # Display help.
      usage
      exit 1
      ;;
  esac
done

check_args(){
  [ "${LEAGUE}x" == "x" ] && echo -e "ERROR: Must specify league!\n" && usage && exit 1
  [ "${DROP_ID}x" == "x" ] && echo -e "ERROR: Must specify id of player to drop!\n" && usage && exit 1
  [ "$NOW" == "true" ] && [ -n "$START_OPT" ] && echo -e "ERROR: Cannot use --now together with -s!\n" && usage && exit 1
}
check_args

[ "$NOW" == "true" ] && START_OPT="--start now"

caffeinate -is fmgr roster drop --league $LEAGUE --drop $DROP_ID $START_OPT