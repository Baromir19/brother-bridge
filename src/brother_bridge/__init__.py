"""Brother P-touch label printing for Python.

``brother-bridge`` parses Brother ``.lbx`` templates, fills their fields and prints
them on Windows through the b-PAC COM SDK or on Linux/macOS through direct
Brother raster output or CUPS.

Quick start::

    from pathlib import Path

    from brother_bridge import (
        LabelData,
        LabelPrinterService,
        LabelTemplate,
        PrintRequest,
    )

    request = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "Ada Lovelace", "address": "London"}),
    )
    LabelPrinterService(Path("templates")).print_label(request)

Low-level pipeline, without hardware::

    from brother_bridge import LbxParser, LbxRenderer

    layout = LbxParser().parse(Path("address.lbx").read_bytes())
    layout.get_object("title").set_text("Ada Lovelace")  # type: ignore[union-attr]
    image = LbxRenderer().render(layout)

Modules are organised by responsibility: :mod:`brother_bridge.lbx` for parsing and
rendering, :mod:`brother_bridge.managers` for platform documents,
:mod:`brother_bridge.printers` for transport backends and
:mod:`brother_bridge.services` for application-level helpers.
"""

from __future__ import annotations

import logging

from .config import PrinterConfig
from .exceptions import (
    BpacConnectionError,
    ConfigurationError,
    LabelAlreadyExistsError,
    LabelAlreadyExistsException,
    LabelDataMissingError,
    LabelFieldNotFoundError,
    LabelTemplateNotFoundError,
    MissingDependencyError,
    PrinterError,
    PrinterStateError,
    UnsupportedLabelError,
)
from .lbx import FontResolver, LbxParser, LbxRenderer
from .lbx.model import LabelLayout, PaperSpec, TextObject
from .managers import LabelDocument, document_factory
from .models import LabelData, LabelTemplate, PrintMode, PrintRequest
from .printers import (
    BrotherQlLabelResolver,
    BrotherQlRasterBackend,
    CupsPngBackend,
    FileBackend,
    PrinterBackend,
)
from .services import LabelPrinterService, LabelTemplateService
from .utils import LbxUtils

__version__ = "1.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "BpacConnectionError",
    "BrotherQlLabelResolver",
    "BrotherQlRasterBackend",
    "ConfigurationError",
    "CupsPngBackend",
    "FileBackend",
    "FontResolver",
    "LabelAlreadyExistsError",
    "LabelAlreadyExistsException",
    "LabelData",
    "LabelDataMissingError",
    "LabelDocument",
    "LabelFieldNotFoundError",
    "LabelLayout",
    "LabelPrinterService",
    "LabelTemplate",
    "LabelTemplateNotFoundError",
    "LabelTemplateService",
    "LbxParser",
    "LbxRenderer",
    "LbxUtils",
    "MissingDependencyError",
    "PaperSpec",
    "PrintMode",
    "PrintRequest",
    "PrinterBackend",
    "PrinterConfig",
    "PrinterError",
    "PrinterStateError",
    "TextObject",
    "UnsupportedLabelError",
    "__version__",
    "document_factory",
]
