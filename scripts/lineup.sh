#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

PROJECT_DIR="$(dirname "$(dirname "$0")")"

# unset required args
unset LEAGUE

# set defaults for optional args
START_OPT=""
END_OPT=""

while getopts "e:hl:s:" opt; do
  case $opt in
    e) # Last date to set lineup.  ISO 8601 date format.
      END_OPT="--end $OPTARG"
      ;;
    h) # Display help text.
      usage
      exit 0
      ;;
    l) # The league name.
      LEAGUE="$OPTARG"
      ;;
    s) # First date to set lineup.  ISO 8601 date format.
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
}
check_args

pushd $PROJECT_DIR
caffeinate -is pipenv run python src/fantasy_manager/cli/__init__.py lineup automate --league $LEAGUE $START_OPT $END_OPT
exit_code=$?
popd

exit $exit_code