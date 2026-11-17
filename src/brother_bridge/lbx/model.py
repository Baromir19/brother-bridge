"""In-memory representation of a parsed ``.lbx`` label.

The dataclasses below are pure data structures. They do not depend on Pillow,
CUPS or the ``.lbx`` container format, which lets the parser, the renderer and
the print backends evolve independently.

Structure::

    LabelLayout
      |- PaperSpec
      `- objects: dict[str, LabelObject]
            |- TextObject     -> FontSpec, list[Run]
            |- BarcodeObject  (parsed, not rendered)
            `- ImageObject    (parsed, not rendered)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from ..exceptions import LabelFieldNotFoundError

PT_PER_INCH: float = 72.0
"""PostScript points per inch."""

PT_TO_MM: float = 25.4 / PT_PER_INCH
"""Conversion factor from PostScript points to millimetres."""


def pt_to_mm(value_pt: float) -> float:
    """Convert a length from PostScript points to millimetres."""
    return value_pt * PT_TO_MM


@dataclass(frozen=True, slots=True)
class FontSpec:
    """Font of a text run, as declared by the template.

    Attributes:
        name: Family name written in the template, e.g. ``"Atlanta"``.
        size_pt: Size in PostScript points.
        bold: Whether the run is bold.
        italic: Whether the run is italic.
        color: Foreground colour as ``"#RRGGBB"``.
    """

    name: str
    size_pt: float
    bold: bool = False
    italic: bool = False
    color: str = "#000000"


@dataclass(slots=True)
class Run:
    """A slice of text that shares one font.

    Mirrors a ``<text:stringItem>`` element. The invariant for every
    :class:`TextObject` is that the lengths of its runs sum to
    ``len(TextObject.text)``.
    """

    length: int
    font: FontSpec


class LabelObject(ABC):
    """Base class of every printable object.

    Objects carry a name (the ``objectName`` of the template), a position and a
    size in PostScript points.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    @property
    @abstractmethod
    def object_type(self) -> Literal["text", "barcode", "image"]:
        """Object kind, used by the renderer to dispatch."""


@dataclass
class TextObject(LabelObject):
    """Text object of a label.

    ``text`` is the canonical content and ``runs`` describes its formatting.
    :meth:`set_text` replaces both with a single run using
    :attr:`default_font`, which is the intended behaviour when a caller injects
    values into a template.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    text: str
    default_font: FontSpec
    runs: list[Run]

    h_align: Literal["LEFT", "CENTER", "RIGHT"] = "LEFT"
    v_align: Literal["TOP", "CENTER", "BOTTOM"] = "TOP"
    shrink: bool = False
    line_space: float = 0.0
    char_space: float = 0.0
    auto_lf: bool = True

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "text"

    def set_text(self, value: str) -> None:
        """Replace the content and collapse the formatting to one run.

        Args:
            value: New text.
        """
        self.text = value
        self.runs = [Run(length=len(value), font=self.default_font)]

    def iter_runs(self) -> list[tuple[str, FontSpec]]:
        """Return the text split into ``(segment, font)`` pairs."""
        result: list[tuple[str, FontSpec]] = []
        offset = 0

        for run in self.runs:
            end = offset + run.length
            result.append((self.text[offset:end], run.font))
            offset = end

        return result


@dataclass
class BarcodeObject(LabelObject):
    """Barcode object of a label.

    Parsed for inspection and future rendering; barcodes are not drawn by
    :class:`~brother_bridge.lbx.renderer.LbxRenderer` yet.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    value: str = ""
    barcode_type: str = "CODE128"

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "barcode"


@dataclass
class ImageObject(LabelObject):
    """Image object of a label.

    Parsed for inspection and future rendering; image payloads are not
    extracted from the container yet.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    data: bytes = field(default_factory=bytes)

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "image"


@dataclass(slots=True)
class PaperSpec:
    """Paper description parsed from ``<style:paper>``.

    Attributes:
        width_pt: Short edge of the tape, in points.
        height_pt: Declared length of the design, in points.
        auto_length: When true, the printed length grows with the content and
            ``height_pt`` is only an editor hint.
        margin_left_pt, margin_top_pt, margin_right_pt, margin_bottom_pt:
            Non-printable margins in points.
        orientation: ``"landscape"`` means the design X axis follows the tape
            length and the Y axis its physical width.
        printer_name: Printer stored in the template, used as a fallback target.
        format_id: Numeric paper format of P-touch Editor. Informational only;
            tape identifiers are resolved from the geometry.
    """

    width_pt: float
    height_pt: float
    auto_length: bool

    margin_left_pt: float = 0.0
    margin_top_pt: float = 0.0
    margin_right_pt: float = 0.0
    margin_bottom_pt: float = 0.0

    orientation: Literal["portrait", "landscape"] = "portrait"
    printer_name: str = ""
    format_id: int = 0

    @property
    def exact_width_mm(self) -> float:
        """Tape width in millimetres without rounding."""
        return pt_to_mm(self.width_pt)

    @property
    def exact_height_mm(self) -> float | None:
        """Declared length in millimetres, or ``None`` for continuous tape."""
        if self.auto_length:
            return None

        return pt_to_mm(self.height_pt)

    @property
    def width_mm(self) -> int:
        """Tape width in millimetres, rounded to an integer."""
        return round(self.exact_width_mm)

    @property
    def height_mm(self) -> int | None:
        """Declared length in millimetres, or ``None`` for continuous tape."""
        exact = self.exact_height_mm

        return None if exact is None else round(exact)


@dataclass
class LabelLayout:
    """Parsed label, ready to be rendered.

    ``objects`` is keyed by ``objectName`` so that field updates are O(1).
    """

    paper: PaperSpec
    objects: dict[str, LabelObject]

    @property
    def text_objects(self) -> dict[str, TextObject]:
        """Text objects of the layout, keyed by name."""
        return {
            name: obj
            for name, obj in self.objects.items()
            if isinstance(obj, TextObject)
        }

    def get_object(self, name: str) -> LabelObject:
        """Return the object named ``name``.

        Raises:
            LabelFieldNotFoundError: If the name is not present.
        """
        try:
            return self.objects[name]
        except KeyError:
            raise LabelFieldNotFoundError(name) from None


__all__ = [
    "PT_PER_INCH",
    "PT_TO_MM",
    "BarcodeObject",
    "FontSpec",
    "ImageObject",
    "LabelLayout",
    "LabelObject",
    "PaperSpec",
    "Run",
    "TextObject",
    "pt_to_mm",
]
