#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

PROJECT_DIR="$(dirname "$(dirname "$0")")"

# unset required args
unset ADD_ID
unset LEAGUE

# set defaults for optional args
START_OPT=""
FAAB_OPT=""
WAIVERS="false"

while getopts "a:f:hl:s:w" opt; do
  case $opt in
    a) # The id of the player to be added.
      ADD_ID="$OPTARG"
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
}
check_args

pushd $PROJECT_DIR
if [[ "$WAIVERS" == "true" ]]; then
    caffeinate -is pipenv run python src/fantasy_manager/cli/__init__.py roster add claim --league $LEAGUE --add $ADD_ID $FAAB_OPT $START_OPT
else
    caffeinate -is pipenv run python src/fantasy_manager/cli/__init__.py roster add --league $LEAGUE --add $ADD_ID $START_OPT
fi
exit_code=$?
popd

exit $exit_code