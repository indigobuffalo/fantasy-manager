# Examples

## Lineup

Command to set lineup based off a roster file:
```commandline
pipenv run python update_roster.py lineup --league-id 12883 --league-number 1 --locked Nurse,Kane --start 2022-10-24 --end 2022-10-31 --roster-file 10-21.yml
```

## Misc

Update _current_leagues.py symbolic link each year to ensure current league data is used.

```
cd config/data/leagues
ln -sf 2025_2026.py _current_leagues.py
```


## TODO

Used argparse to enforce cli arg types
