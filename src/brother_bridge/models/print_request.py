"""Description of a single print job."""

from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ConfigurationError
from .label_data import LabelData
from .label_template import LabelTemplate


@dataclass
class PrintRequest:
    """A template, the values to inject and the job parameters.

    Attributes:
        label: Template to print.
        data: Field values, keyed by template object name.
        copies: Number of copies; must be at least one.
        printer: Target printer or queue name. An empty string selects the
            platform default (or the printer stored in the template).
    """

    label: LabelTemplate
    data: LabelData
    copies: int = 1
    printer: str = ""

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ConfigurationError("copies", f"must be at least 1: {self.copies}")

        self.printer = self.printer.strip()

    def missing_fields(self) -> tuple[str, ...]:
        """Return template fields that have no value in :attr:`data`."""
        return tuple(field for field in self.label.fields if field not in self.data)


__all__ = ["PrintRequest"]
