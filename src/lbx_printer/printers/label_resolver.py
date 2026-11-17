"""Resolve ``brother_ql`` tape identifiers from template geometry.

P-touch Editor stores physical paper dimensions in PostScript points and a
numeric format identifier that is only meaningful to the editor. Instead of
maintaining a hard-coded format table, this module converts the dimensions to
millimetres and picks the nearest ``brother_ql`` label of the same kind
(continuous or die-cut). Labels added to ``brother_ql`` in the future are
therefore recognised automatically.

``brother_ql`` is imported lazily so that the package stays importable on
Windows, where the b-PAC backend does not need it.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from ..exceptions import MissingDependencyError, UnsupportedLabelError
from ..i18n import translate
from ..lbx.model import PaperSpec

logger = logging.getLogger(__name__)

MAX_DISTANCE_MM = 2.0
"""Maximum geometric distance, in millimetres, accepted as a match.

Continuous tape uses the absolute width difference, die-cut labels use the
Euclidean distance in width and height. Two millimetres absorb rounding errors
from the point-to-millimetre conversion while still rejecting unrelated sizes.
"""

_MISSING_HINT = "Install the optional dependency: pip install 'lbx-printer[brother]'"


def _load_catalogue() -> tuple[Any, Any]:
    """Return ``(ALL_LABELS, FormFactor)`` from ``brother_ql``."""
    try:
        from brother_ql.labels import ALL_LABELS, FormFactor
    except ImportError as exc:
        raise MissingDependencyError("brother_ql", _MISSING_HINT) from exc

    return ALL_LABELS, FormFactor


@dataclass(frozen=True, slots=True)
class LabelGeometry:
    """Geometry of a ``brother_ql`` label.

    Attributes:
        name: ``brother_ql`` identifier, e.g. ``"62"`` or ``"103x164"``.
        width_mm: Tape width in millimetres.
        height_mm: Label height in millimetres, ``None`` for continuous tape.
        continuous: Whether the tape has no fixed length.
    """

    name: str
    width_mm: float
    height_mm: float | None
    continuous: bool


class BrotherQlLabelResolver:
    """Match a :class:`PaperSpec` against the ``brother_ql`` label catalogue.

    The catalogue is read once during construction and never mutated, so the
    instance is safe to share between threads.

    Raises:
        MissingDependencyError: If ``brother_ql`` is not installed.
    """

    def __init__(self) -> None:
        self._labels: tuple[LabelGeometry, ...] = self._build_labels()

    @staticmethod
    def _build_labels() -> tuple[LabelGeometry, ...]:
        all_labels, form_factor = _load_catalogue()
        continuous_factors = (form_factor.ENDLESS, form_factor.PTOUCH_ENDLESS)

        geometries: list[LabelGeometry] = []

        for label in all_labels:
            continuous = label.form_factor in continuous_factors

            geometries.append(
                LabelGeometry(
                    name=label.identifier,
                    width_mm=float(label.tape_size[0]),
                    height_mm=None if continuous else float(label.tape_size[1]),
                    continuous=continuous,
                )
            )

        logger.debug("Loaded geometry for %d brother_ql labels.", len(geometries))

        return tuple(geometries)

    def resolve(self, paper: PaperSpec) -> str:
        """Return the ``brother_ql`` identifier closest to ``paper``.

        Args:
            paper: Paper description parsed from the ``.lbx`` template.

        Returns:
            Label identifier such as ``"62"`` or ``"103x164"``.

        Raises:
            UnsupportedLabelError: If the closest label is further away than
                :data:`MAX_DISTANCE_MM`, or no label of the same kind exists.
        """
        width_mm = paper.exact_width_mm
        height_mm = paper.exact_height_mm
        candidates = [
            label for label in self._labels if label.continuous == paper.auto_length
        ]

        if not candidates:
            kind = "continuous" if paper.auto_length else "die-cut"

            raise UnsupportedLabelError(
                translate(
                    "unsupported_label_kind",
                    kind=kind,
                    width=f"{width_mm:.1f}",
                    height="auto" if height_mm is None else f"{height_mm:.1f}",
                )
            )

        best, distance = self._closest(candidates, width_mm, height_mm)

        if distance > MAX_DISTANCE_MM:
            raise UnsupportedLabelError(
                translate(
                    "unsupported_label",
                    width=f"{width_mm:.1f}",
                    height="auto" if height_mm is None else f"{height_mm:.1f}",
                    continuous=paper.auto_length,
                    name=best.name,
                    distance=distance,
                    threshold=MAX_DISTANCE_MM,
                )
            )

        logger.debug(
            "Resolved tape %sx%s mm to %r (%sx%s mm, distance %.2f mm).",
            f"{width_mm:.1f}",
            "auto" if height_mm is None else f"{height_mm:.1f}",
            best.name,
            best.width_mm,
            best.height_mm if best.height_mm is not None else "auto",
            distance,
        )

        return best.name

    @staticmethod
    def _closest(
        candidates: list[LabelGeometry],
        width_mm: float,
        height_mm: float | None,
    ) -> tuple[LabelGeometry, float]:
        if height_mm is None:
            best = min(candidates, key=lambda label: abs(label.width_mm - width_mm))

            return best, abs(best.width_mm - width_mm)

        def distance(label: LabelGeometry) -> float:
            if label.height_mm is None:
                return math.inf

            return math.hypot(label.width_mm - width_mm, label.height_mm - height_mm)

        best = min(candidates, key=distance)

        return best, distance(best)


__all__ = [
    "MAX_DISTANCE_MM",
    "BrotherQlLabelResolver",
    "LabelGeometry",
    "UnsupportedLabelError",
]
