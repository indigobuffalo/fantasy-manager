"""Shared helpers for structured CLI output (``--output text|json|yaml``).

Commands parse ``--output`` into an :class:`OutputFormat`, run, and return it on
``CommandResult.output_format`` alongside the ``data`` payload. For
``json``/``yaml`` the top-level runner serializes that payload to stdout.
Diagnostic/framing log lines stay on stderr, so ``jq``/``yq`` get a clean stdout
stream. Keeping the parse in one place (the command's docopt options) means the
runner never has to re-interpret the command line and can't disagree about the
requested format.

Because ``json`` and ``yaml`` are just two serializations of the same payload,
supporting both is nearly free once a command fills in ``data``.
"""

from enum import Enum
import json

import yaml

from fantasy_manager.exceptions import InputError


class OutputFormat(Enum):
    """The supported ``--output`` formats."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"

    @property
    def is_structured(self) -> bool:
        """Whether this format emits a machine-readable payload (vs. log lines)."""
        return self is not OutputFormat.TEXT


def parse_output_format(value: str | None) -> OutputFormat:
    """Coerce a raw ``--output`` value into an :class:`OutputFormat`.

    ``None`` (flag omitted) defaults to ``text``. An unrecognized value is a
    user error, surfaced as a clean ``InputError`` rather than a raw ``KeyError``.
    """
    if value is None:
        return OutputFormat.TEXT
    try:
        return OutputFormat(value.lower())
    except ValueError:
        choices = ", ".join(fmt.value for fmt in OutputFormat)
        raise InputError(f"--output must be one of: {choices} (got '{value}').")


def serialize(data, output_format: OutputFormat) -> str:
    """Serialize a payload for the given structured format.

    Only ``json`` and ``yaml`` are serialized here; ``text`` is rendered by the
    command itself as human-readable log lines, so calling this with ``TEXT`` is
    a programming error.
    """
    if output_format is OutputFormat.JSON:
        return json.dumps(data, indent=2, ensure_ascii=False)
    if output_format is OutputFormat.YAML:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip("\n")
    raise ValueError(f"{output_format} is not a structured (serializable) format.")
