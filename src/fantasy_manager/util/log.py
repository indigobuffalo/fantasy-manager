from logging import Logger


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
    """Uses max key length in a list of key-val pairs to determine the total
    padding required to align all pairs when printing them line by line.

    Args:
        tuples (list[tuple[str, str]]): A list of key-value pairs.
        padding (int): The desired minimum padding between each key-val pair.

    Returns:
        int: The number of spaces to use in ljust when printing the key-value pairs.
    """
    max_label_len = max(map(len, [t[0] for t in tuples]))
    return padding + max_label_len


def log_pairs(
    logger: Logger,
    tuples: list[tuple[str, str]],
    padding: int = 2,
    separator: str = ":",
    default_val: str = "-",
) -> None:
    """Log prettily the passed list of label-value pairs.

    Args:
        logger (Logger):                  The logger to use.
        tuples (list[tuple[str, str]]):   A list of tuples containing label-value pairs.
        padding (int):                    The min padding between the labels and values.
        default (str):                    The default to use when a value is None.
    """
    log_line_break(logger)
    padding = get_key_adjusted_padding(tuples, padding)
    for label, val in tuples:
        logger.info(
            label + separator.ljust(padding - len(label)) + (val or default_val)
        )
    log_line_break(logger)


def align_pairs(
    tuples: list[tuple[str, str]], padding: int = 2, separator: str = ":"
) -> list[str]:
    """Joins each pair in the passed tuple with consistent alignment for pretty logging.

    Args:
        tuples (list[tuple[str, str]]): The list of key-val pairs to join.
        padding (int, optional): The minimum spacing between each joined key-val pairs. Defaults to 2.
        separator (str, optional): The separator to use between each joined key-val pair. Defaults to ":".

    Returns:
        list[str]: Strings of joined key-val pairs which will be aligned when printed line-by-line.
    """
    padding = get_key_adjusted_padding(tuples, padding)
    adjusted_tuples = []
    for label, val in tuples:
        adjusted_tuples.append(label + separator.ljust(padding - len(label)) + val)
    return adjusted_tuples
