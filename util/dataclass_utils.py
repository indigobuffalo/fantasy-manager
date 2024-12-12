"""Utility methods for working with dataclasses"""
from dataclasses import asdict, fields
from typing import Type, TypeVar


T = TypeVar("T", bound="dataclass")


def prune_dict(cls: Type[T], data: dict) -> dict:
    """Remove any keys from the passed data dict
    which are not names of attributes of the passed
    data class type.

    Args:
        cls (Type[T]): A type which is decorated by the dataclass
        data (dict): A data dict holding used to instantiate a class of type `cls`.

    Returns:
        dict: A data dict with any keys whose names don't match attributes of `cls` removed.
    """
    valid_fields = {field.name for field in fields(cls)}
    return {key: value for key, value in data.items() if key in valid_fields}


def filtered_asdict(cls: Type[T], exclude: set[str] = None) -> dict:
    """Generate a dictionary representation of a dataclass, excluding specific fields."""
    exclude = exclude or set()
    return asdict(
        cls, dict_factory=lambda items: {k: v for k, v in items if k not in exclude}
    )
