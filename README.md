# Setup

## Local Development

Setup python environment:
```
brew install uv

# setup virtual environment and install dependencies
uv venv
uv sync --dev

# install the project in editable mode for local development
uv pip install -e
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
