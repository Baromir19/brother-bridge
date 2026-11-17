"""Configuration objects for the printing pipeline.

Configuration is plain data: :class:`PrinterConfig` is an immutable dataclass
that can be built explicitly, from environment variables or from both, and is
passed to the factories instead of being read from global state. This keeps the
library usable in-process, in tests and in containers without hidden coupling.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError

DEFAULT_HOST = "10.10.4.44"
DEFAULT_MODEL = "QL-1110NWB"
DEFAULT_PORT = 9100
DEFAULT_DPI = 300
DEFAULT_THRESHOLD = 70.0

ENV_HOST = "LBX_PRINTER_HOST"
ENV_MODEL = "LBX_PRINTER_MODEL"
ENV_LABEL = "LBX_PRINTER_LABEL"
ENV_PORT = "LBX_PRINTER_PORT"
ENV_CUT = "LBX_PRINTER_CUT"
ENV_THRESHOLD = "LBX_PRINTER_THRESHOLD"
ENV_DITHER = "LBX_PRINTER_DITHER"
ENV_DPI = "LBX_PRINTER_DPI"
ENV_TEMPLATE_DIR = "LBX_PRINTER_TEMPLATE_DIR"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def _parse_bool(field: str, raw: str) -> bool:
    value = raw.strip().lower()

    if value in _TRUTHY:
        return True

    if value in _FALSY:
        return False

    raise ConfigurationError(field, f"expected a boolean, got {raw!r}")


def _parse_int(field: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(field, f"expected an integer, got {raw!r}") from exc


def _parse_float(field: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(field, f"expected a number, got {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class PrinterConfig:
    """Settings needed to reach and drive a label printer.

    Attributes:
        host: Network address of a Brother QL printer (raster backend).
        model: Brother QL model name understood by ``brother_ql``.
        label: Explicit ``brother_ql`` label identifier. ``None`` lets the
            renderer resolve the tape from the template geometry.
        port: Raw TCP port of the printer (JetDirect, 9100 by default).
        cut: Cut the tape after each copy.
        threshold: Black/white threshold in percent for the raster backend.
        dither: Dither instead of thresholding; ignored when ``threshold`` is
            exact and the image is already monochrome.
        dpi: Rendering resolution. Brother QL printers are 300 DPI native.
        template_dir: Directory that stores ``.lbx`` templates.
    """

    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    label: str | None = None
    port: int = DEFAULT_PORT
    cut: bool = True
    threshold: float = DEFAULT_THRESHOLD
    dither: bool = False
    dpi: int = DEFAULT_DPI
    template_dir: Path | None = None

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ConfigurationError("host", "must not be empty")

        if not self.model.strip():
            raise ConfigurationError("model", "must not be empty")

        if not 0 < self.port < 65536:
            raise ConfigurationError("port", f"out of range: {self.port}")

        if self.dpi <= 0:
            raise ConfigurationError("dpi", f"must be positive: {self.dpi}")

        if not 0 <= self.threshold <= 100:
            raise ConfigurationError(
                "threshold", f"must be within 0..100: {self.threshold}"
            )

        if self.label is not None and not self.label.strip():
            raise ConfigurationError("label", "use None to enable auto-detection")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PrinterConfig:
        """Build a configuration from environment variables.

        Recognised variables are the ``ENV_*`` constants of this module. Absent
        variables keep their default value; malformed values raise
        :class:`~lbx_printer.exceptions.ConfigurationError`.

        Args:
            env: Mapping to read instead of :data:`os.environ`.

        Returns:
            A validated configuration.
        """
        source = os.environ if env is None else env

        values: dict[str, Any] = {}

        if (raw := source.get(ENV_HOST)) is not None:
            values["host"] = raw

        if (raw := source.get(ENV_MODEL)) is not None:
            values["model"] = raw

        if (raw := source.get(ENV_LABEL)) is not None:
            values["label"] = raw or None

        if (raw := source.get(ENV_PORT)) is not None:
            values["port"] = _parse_int("port", raw)

        if (raw := source.get(ENV_CUT)) is not None:
            values["cut"] = _parse_bool("cut", raw)

        if (raw := source.get(ENV_THRESHOLD)) is not None:
            values["threshold"] = _parse_float("threshold", raw)

        if (raw := source.get(ENV_DITHER)) is not None:
            values["dither"] = _parse_bool("dither", raw)

        if (raw := source.get(ENV_DPI)) is not None:
            values["dpi"] = _parse_int("dpi", raw)

        if (raw := source.get(ENV_TEMPLATE_DIR)) is not None:
            values["template_dir"] = Path(raw)

        return cls(**values)

    def with_overrides(self, **changes: Any) -> PrinterConfig:
        """Return a copy of this configuration with selected fields replaced.

        Args:
            **changes: Field names and their new values.

        Returns:
            A new validated configuration.

        Raises:
            TypeError: If a field name is unknown.
        """
        return dataclasses.replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-friendly representation of the settings."""
        return {
            "host": self.host,
            "model": self.model,
            "label": self.label,
            "port": self.port,
            "cut": self.cut,
            "threshold": self.threshold,
            "dither": self.dither,
            "dpi": self.dpi,
            "template_dir": str(self.template_dir) if self.template_dir else None,
        }


__all__ = [
    "DEFAULT_DPI",
    "DEFAULT_HOST",
    "DEFAULT_MODEL",
    "DEFAULT_PORT",
    "DEFAULT_THRESHOLD",
    "ENV_CUT",
    "ENV_DITHER",
    "ENV_DPI",
    "ENV_HOST",
    "ENV_LABEL",
    "ENV_MODEL",
    "ENV_PORT",
    "ENV_TEMPLATE_DIR",
    "ENV_THRESHOLD",
    "PrinterConfig",
]
