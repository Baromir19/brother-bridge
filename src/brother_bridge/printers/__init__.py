"""Print backends and tape resolution.

Available backends:

* :class:`~brother_bridge.printers.cups_png.CupsPngBackend` - PNG over
  ``lp`` stdin, no temporary files.
* :class:`~brother_bridge.printers.brother_ql_raster.BrotherQlRasterBackend` -
  raw Brother raster data over TCP, no CUPS or driver required.
* :class:`~brother_bridge.printers.file_backend.FileBackend` - writes image files,
  useful for previews, tests and hardware-free debugging.
"""

from .backend import PrinterBackend
from .brother_ql_raster import BrotherQlRasterBackend
from .cups_png import CupsPngBackend
from .file_backend import FileBackend
from .label_resolver import (
    MAX_DISTANCE_MM,
    BrotherQlLabelResolver,
    LabelGeometry,
    UnsupportedLabelError,
)

__all__ = [
    "MAX_DISTANCE_MM",
    "BrotherQlLabelResolver",
    "BrotherQlRasterBackend",
    "CupsPngBackend",
    "FileBackend",
    "LabelGeometry",
    "PrinterBackend",
    "UnsupportedLabelError",
]
