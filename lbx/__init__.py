"""
Package ``lbx`` - pipeline de traitement des documents Brother .lbx.

Expose les composants principaux du pipeline en mémoire :

- :class:`~lbx.parser.LbxParser`    - ZIP bytes -> :class:`~lbx.model.LabelLayout`
- :class:`~lbx.renderer.LbxRenderer` - :class:`~lbx.model.LabelLayout` -> PIL.Image
- :class:`~lbx.fonts.FontResolver`   - résolution de polices TTF
- Modèle de données : :mod:`lbx.model`
"""

from .fonts import FontResolver
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
from .renderer import LbxRenderer

__all__ = [
    # Parser
    "LbxParser",
    # Renderer
    "LbxRenderer",
    # Polices
    "FontResolver",
    # Modèle
    "LabelLayout",
    "PaperSpec",
    "LabelObject",
    "TextObject",
    "BarcodeObject",
    "ImageObject",
    "FontSpec",
    "Run",
]
