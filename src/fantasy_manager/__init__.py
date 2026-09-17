import logging
import sys
from fantasy_manager.config.config import FantasyConfig

# Configure the root logger
LOG_LEVEL = getattr(logging, FantasyConfig.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOG_LEVEL,
    stream=sys.stderr,
)

# Configure a dedicated stdout logger
STDOUT = logging.getLogger("stdout")
STDOUT.propagate = False
_STDOUT_STREAM = logging.StreamHandler(sys.stdout)
_STDOUT_STREAM.setLevel(LOG_LEVEL)
_STDOUT_STREAM.setFormatter(logging.Formatter("%(message)s"))
STDOUT.addHandler(_STDOUT_STREAM)

# Ensure noisy loggers don’t double-log
noisy_loggers = ["yahoo_oauth"]
for logger_name in noisy_loggers:
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    for handler in logger.handlers[:]:  # Remove existing handlers
        logger.removeHandler(handler)
