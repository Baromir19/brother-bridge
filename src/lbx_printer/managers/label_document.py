"""Abstract base class for label document managers.

A document manager owns the platform-specific work of opening a template,
writing field values and submitting the job. The base class implements the
parts that are identical everywhere (path validation, value stringification,
context management) and delegates the rest to hooks, following the template
method pattern::

    with document_factory(config) as doc:
        doc.open(template_path)
        doc.set_field("reference", "REF-001")
        doc.print(copies=2)

Subclasses implement :meth:`_open`, :meth:`_set_field` and :meth:`print`, and
may override :meth:`_initialize` and :meth:`close` to manage resources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any

from ..exceptions import LabelTemplateNotFoundError


class LabelDocument(ABC):
    """Contract shared by every platform implementation."""

    def __enter__(self) -> LabelDocument:
        self._initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def open(self, path: str | Path) -> None:
        """Open a template file.

        Args:
            path: Path to the ``.lbx`` file.

        Raises:
            LabelTemplateNotFoundError: If the file does not exist.
        """
        resolved = Path(path)

        if not resolved.is_file():
            raise LabelTemplateNotFoundError(resolved)

        self._open(resolved)

    def set_field(self, name: str, value: Any) -> None:
        """Assign a text value to a template field.

        Args:
            name: Object name declared in the template.
            value: Any value; it is converted with :class:`str`.
        """
        self._set_field(name, str(value))

    def set_fields(self, values: Mapping[str, Any]) -> None:
        """Assign several fields in one call.

        Args:
            values: Mapping of object name to value.
        """
        for name, value in values.items():
            self.set_field(name, value)

    def _initialize(self) -> None:
        """Acquire platform resources. Called by ``__enter__``."""
        return None

    def close(self) -> None:
        """Release platform resources. Called by ``__exit__``."""
        return None

    @abstractmethod
    def _open(self, path: Path) -> None:
        """Open the template at platform level.

        Args:
            path: Validated path to an existing template file.
        """

    @abstractmethod
    def _set_field(self, name: str, value: str) -> None:
        """Write ``value`` into the field ``name`` at platform level."""

    @abstractmethod
    def print(self, copies: int = 1, printer: str = "") -> bool:
        """Print the document.

        Args:
            copies: Number of copies.
            printer: Target printer or queue; an empty string selects the
                platform default.

        Returns:
            ``True`` when the job was submitted.
        """


__all__ = ["LabelDocument"]
