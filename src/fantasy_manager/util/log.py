from logging import Logger
from operator import itemgetter


def log_line_break(
    logger: Logger, spacer: str = "-", count: int = 60, lines: int = 1
) -> None:
    """Log line breaks for framing log messages.

    Args:
        logger (Logger):         The logger to use.
        spacer (str, optional):  The character to use to create the line break. Defaults to "=".
        count (int, optional):   The number of times to repeat the spacer. Defaults to 65=.
        lines (int, optional):   The number of consecutive line breaks to log. Defaults to 1.
    """
    for _ in range(lines):
        logger.info(spacer * count)


def get_key_adjusted_padding(tuples: list[tuple[str, str]], padding: int) -> int:
    """Factors key lengths into padding to ensure proper ljust/rjust alignment.

    Args:
        tuples (list[tuple[str, str]]): A list of key-value pairs.
        padding (int): The desired minimum padding between each key-val pair.

    Returns:
        int: The number of spaces to use in ljust when printing the key-value pairs.
    """
    longest_label = max(tuples, key=itemgetter(0))[0]
    return padding + len(longest_label)


def log_tuples(
    logger: Logger, tuples: list[tuple[str, str]], padding: int = 2, default: str = "-"
) -> None:
    """Log prettily the passed list of label-value tuples.

    Args:
        logger (Logger):                  The logger to use.
        tuples (list[tuple[str, str]]):   A list of tuples containing label-value pairs.
        padding (int):                    The min padding between the labels and values.
        default (str):                    The default to use when a value is None.
    """
    padding = get_key_adjusted_padding(tuples, padding)
    for label, val in tuples:
        logger.info(label + ":".ljust(padding - len(label)) + (val or default))


def join_with_padding(
    tuples: list[tuple[str, str]], padding: int = 2, separator: str = ":"
):
    """Joins each pair in the passed tuple with consistent alignment for pretty logging.

    Args:
        tuples (list[tuple[str, str]]): The list of key-val pairs to join.
        padding (int, optional): The minimum spacing between each joined key-val pairs. Defaults to 2.
        separator (str, optional): The separator to use between each joined key-val pair. Defaults to ":".

    Returns:
        _type_: _description_
    """
    padding = get_key_adjusted_padding(tuples, padding)
    adjusted_tuples = []
    for label, val in tuples:
        adjusted_tuples.append(label + separator.ljust(padding - len(label)) + val)
    return adjusted_tuples
