"""Text values injected into a label template."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field


@dataclass
class LabelData:
    """Field values keyed by the object name used in the template.

    Example:
        >>> data = LabelData({"title": "Ada Lovelace", "address": "London"})
        >>> data["title"]
        'Ada Lovelace'
    """

    values: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.values = {str(key): str(value) for key, value in self.values.items()}

    def __getitem__(self, key: str) -> str:
        return self.values[key]

    def __contains__(self, key: object) -> bool:
        return key in self.values

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return the value for ``key``, or ``default`` when it is absent."""
        return self.values.get(key, default)

    def as_dict(self) -> dict[str, str]:
        """Return a shallow copy of the field values."""
        return dict(self.values)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> LabelData:
        """Build label data from any string-to-value mapping."""
        return cls({str(key): str(value) for key, value in mapping.items()})


__all__ = ["LabelData"]
