"""High-level printing service.

The service depends on the abstract :class:`LabelDocument` only. The concrete
implementation is supplied by a factory, which keeps the service free of
platform branches and easy to test with a fake document.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from ..exceptions import LabelDataMissingError
from ..managers import LabelDocument
from ..managers import document_factory as _default_factory
from ..models import PrintRequest

logger = logging.getLogger(__name__)


class LabelPrinterService:
    """Validate a print request and submit it through a document manager.

    Args:
        template_dir: Directory that holds the ``.lbx`` templates.
        document_factory: Callable returning a :class:`LabelDocument`. Defaults
            to :func:`brother_bridge.managers.document_factory`, which selects the
            implementation for the current platform.

    Example:
        >>> service = LabelPrinterService(Path("templates"))
        >>> service.print_label(request)
        True
    """

    def __init__(
        self,
        template_dir: str | Path,
        document_factory: Callable[[], LabelDocument] | None = None,
    ) -> None:
        self.template_dir = Path(template_dir)
        self._document_factory = (
            _default_factory if document_factory is None else document_factory
        )

    def print_label(self, request: PrintRequest) -> bool:
        """Print one label described by ``request``.

        Args:
            request: Template, values and job parameters.

        Returns:
            ``True`` when the job was submitted.

        Raises:
            LabelTemplateNotFoundError: If the template file is missing.
            LabelDataMissingError: If a required field has no value.
        """
        template_path = request.label.resolve(self.template_dir)
        missing = request.missing_fields()

        if missing:
            raise LabelDataMissingError(missing)

        logger.debug(
            "Printing %r with %d field(s), %d copy(ies) to %r.",
            request.label.name,
            len(request.data),
            request.copies,
            request.printer or "(default)",
        )

        with self._document_factory() as document:
            document.open(template_path)
            document.set_fields(request.data.values)

            return document.print(copies=request.copies, printer=request.printer)


__all__ = ["LabelPrinterService"]
