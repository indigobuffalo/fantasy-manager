#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

PROJECT_DIR="$HOME/code/personal/fantasy-manager"

# unset required args
unset ADD_ID
unset LEAGUE

# set defaults for optional args
DROP_OPT=""
FAAB_OPT=""
NOW_OPT=""
START_OPT=""
WAIVER_OPT=""

while getopts "a:d:f:hl:ns:w" opt; do
  case $opt in
    a) # The id of the player to be added.
      ADD_ID="$OPTARG"
      ;;
    d) # The id of the player to be dropped.
      DROP_OPT="--drop $OPTARG"
      ;;
    f) # Amount of faab to spend.
      FAAB_OPT="--faab $OPTARG"
      ;;
    h) # Display help text.
      usage
      exit 0
      ;;
    l) # The league name.
      LEAGUE="$OPTARG"
      ;;
    n) # Add the player immediately.
      NOW_OPT="--now"
      ;;
    s) # ISO 8601 time stamp which sets the time to add the player.
      START_OPT="--start $OPTARG"
      ;;
    w) # Add the player immediately.
      WAIVER_OPT="--waiver"
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
}
check_args

pushd $PROJECT_DIR
caffeinate -is pipenv run python src/fantasy_manager/cli/roster.py roster --league $LEAGUE --add $ADD_ID $DROP_OPT $START_OPT $NOW_OPT $WAIVER_OPT $FAAB_OPT
popd
