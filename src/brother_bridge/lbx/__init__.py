"""In-memory ``.lbx`` pipeline: parse, edit and render label templates.

The three public entry points are:

* :class:`~brother_bridge.lbx.parser.LbxParser` - archive bytes to
  :class:`~brother_bridge.lbx.model.LabelLayout`.
* :class:`~brother_bridge.lbx.renderer.LbxRenderer` - layout to
  :class:`PIL.Image.Image`.
* :class:`~brother_bridge.lbx.fonts.FontResolver` - template font names to
  available fonts.
"""

from .fonts import DEFAULT_SUBSTITUTIONS, FontResolver
from .model import (
    BarcodeObject,
    FontSpec,
    ImageObject,
    LabelLayout,
    LabelObject,
    PaperSpec,
    Run,
    TextObject,
)
from .parser import LbxParser
from .renderer import DEFAULT_DPI, LbxRenderer

__all__ = [
    "DEFAULT_DPI",
    "DEFAULT_SUBSTITUTIONS",
    "BarcodeObject",
    "FontResolver",
    "FontSpec",
    "ImageObject",
    "LabelLayout",
    "LabelObject",
    "LbxParser",
    "LbxRenderer",
    "PaperSpec",
    "Run",
    "TextObject",
]
