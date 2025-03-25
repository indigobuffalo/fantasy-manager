# Setup

## Local Development

Setup python environment:
```
brew install uv
uv venv
uv sync --dev
```

# Examples

See scripts under the scripts directory

## Misc

Update _current_leagues.py symbolic link each year to ensure current league data is used.

```
cd config/data/leagues
ln -sf 2025_2026.py _current_leagues.py
```


## TODO

- Used argparse to enforce cli arg types
- Check inputs 30 seconds before execution time to save time.
