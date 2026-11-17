"""Exception hierarchy of :mod:`lbx_printer`.

Every error raised by the package derives from :class:`PrinterError`, so a
single ``except PrinterError`` guard is enough to isolate label handling.
Messages are translated through :mod:`lbx_printer.i18n`; the structured
attributes of each exception stay available for programmatic handling.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .i18n import translate


class PrinterError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(PrinterError):
    """Raised when a configuration value is missing or invalid."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(translate("config_invalid", field=field, reason=reason))


class MissingDependencyError(PrinterError):
    """Raised when an optional runtime dependency is not installed.

    Args:
        dependency: Import name or distribution that is missing.
        hint: Additional installation guidance appended to the message.
    """

    def __init__(self, dependency: str, hint: str = "") -> None:
        self.dependency = dependency
        self.hint = hint
        message = translate("missing_dependency", dependency=dependency)
        super().__init__(f"{message} {hint}".strip())


class LabelTemplateNotFoundError(PrinterError):
    """Raised when a template file cannot be located or opened."""

    def __init__(self, target: str | Path) -> None:
        self.target = target
        super().__init__(translate("template_not_found", target=target))


class LabelAlreadyExistsError(PrinterError):
    """Raised when a template with the same name is already registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(translate("template_exists", name=name))


# Historical name kept for source compatibility with earlier revisions.
LabelAlreadyExistsException = LabelAlreadyExistsError


class LabelFieldNotFoundError(PrinterError):
    """Raised when a field name is absent from the template."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(translate("field_not_found", name=name))


class LabelDataMissingError(PrinterError):
    """Raised when required template fields have no value."""

    def __init__(self, fields: Iterable[str]) -> None:
        self.fields = tuple(sorted(fields))
        super().__init__(translate("data_missing", fields=", ".join(self.fields)))


class PrinterStateError(PrinterError):
    """Raised when a document is used before it has been opened.

    Args:
        message: Optional override; a localised default is used otherwise.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or translate("document_not_open"))


class BpacConnectionError(PrinterError):
    """Raised when the Brother b-PAC COM SDK cannot be initialised."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(translate("bpac_unavailable", reason=reason))


class UnsupportedLabelError(PrinterError, ValueError):
    """Raised when no ``brother_ql`` label matches the template geometry."""


__all__ = [
    "BpacConnectionError",
    "ConfigurationError",
    "LabelAlreadyExistsError",
    "LabelAlreadyExistsException",
    "LabelDataMissingError",
    "LabelFieldNotFoundError",
    "LabelTemplateNotFoundError",
    "MissingDependencyError",
    "PrinterError",
    "PrinterStateError",
    "UnsupportedLabelError",
]
