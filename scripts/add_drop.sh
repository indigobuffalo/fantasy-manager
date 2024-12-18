#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

PROJECT_DIR="$HOME/code/personal/yahoo-fantasy"

# unset required args
unset ADD_ID
unset LEAGUE

# set defaults for optional args
NOW_OPT=""
DROP_OPT=""
START_OPT=""

while getopts "a:d:hl:ns:" opt; do
  case $opt in
    a) # The id of the player to be added.
      ADD_ID="$OPTARG"
      ;;
    d) # The id of the player to be dropped.
      DROP_OPT="--drop $OPTARG"
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
caffeinate -is pipenv run python cli.py waivers --league $LEAGUE --add $ADD_ID $DROP_OPT $START_OPT $NOW_OPT
popd
