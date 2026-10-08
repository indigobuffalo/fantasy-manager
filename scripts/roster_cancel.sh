#!/usr/bin/env bash

usage() { echo "$0 usage:" && grep " .)\ #" $0; exit 0; }
[ $# -eq 0 ] && usage

# unset required args
unset ADD_ID
unset LEAGUE

# set defaults for optional args
DROP_OPT=""

while getopts "a:d:hl:" opt; do
  case $opt in
    a) # The id of the claimed (to-be-added) player.
      ADD_ID="$OPTARG"
      ;;
    d) # The id of the player the claim would drop (omit for an add-only claim).
      DROP_OPT="--drop $OPTARG"
      ;;
    h) # Display help text.
      usage
      exit 0
      ;;
    l) # The league name.
      LEAGUE="$OPTARG"
      ;;
    ?) # Display help.
      usage
      exit 1
      ;;
  esac
done

check_args(){
  [ "${LEAGUE}x" == "x" ] && echo -e "ERROR: Must specify league!\n" && usage && exit 1
  [ "${ADD_ID}x" == "x" ] && echo -e "ERROR: Must specify id of claimed player to cancel!\n" && usage && exit 1
}
check_args

caffeinate -is fmgr roster cancel claim --league $LEAGUE --add $ADD_ID $DROP_OPT
