#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

PROJECT_DIR="$HOME/code/personal/fantasy-manager"

# unset required args
unset ADD_ID
unset DROP_ID
unset LEAGUE

# set defaults for optional args
START_OPT=""

while getopts "a:d:hl:s:" opt; do
  case $opt in
    a) # The id of the player to be added.
      ADD_ID="$OPTARG"
      ;;
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
  [ "${ADD_ID}x" == "x" ] && echo -e "ERROR: Must specify id of player to add!\n" && usage && exit 1
  [ "${DROP_ID}x" == "x" ] && echo -e "ERROR: Must specify id of player to drop!\n" && usage && exit 1
}
check_args

pushd $PROJECT_DIR
caffeinate -is pipenv run python src/fantasy_manager/cli/__init__.py roster replace --league $LEAGUE --add $ADD_ID --drop $DROP_ID $START_OPT $NOW_OPT 
exit_code=$?
popd

exit $exit_code