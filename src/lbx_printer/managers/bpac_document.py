"""Windows document manager built on the Brother b-PAC COM SDK.

``bpac`` is a Windows-only COM automation library shipped with the Brother
b-PAC SDK. Both ``pythoncom`` and ``win32com`` are imported lazily so the module
stays importable on other platforms and in test environments.

COM objects are apartment-bound: create and use one document per thread, and
always close it so the apartment is released.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..exceptions import (
    BpacConnectionError,
    LabelFieldNotFoundError,
    LabelTemplateNotFoundError,
    PrinterStateError,
)
from ..models import PrintMode
from .label_document import LabelDocument

logger = logging.getLogger(__name__)

DEFAULT_JOB_NAME = "lbx-printer"
_MISSING_HINT = "Install the pywin32 package: pip install 'lbx-printer[windows]'."


class BpacDocument(LabelDocument):
    """Drive a Brother printer through the b-PAC COM SDK.

    Example:
        >>> with BpacDocument() as doc:
        ...     doc.open("address.lbx")
        ...     doc.set_field("title", "Ada Lovelace")
        ...     doc.print(copies=1)
        True
    """

    def __init__(self, job_name: str = DEFAULT_JOB_NAME) -> None:
        self._doc: Any = None
        self._job_name = job_name
        self._com_initialized = False

    def _initialize(self) -> None:
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise BpacConnectionError(f"{exc}. {_MISSING_HINT}") from exc

        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)

        try:
            document = win32com.client.DispatchEx("bpac.Document")

            if document is None:
                raise RuntimeError("DispatchEx('bpac.Document') returned None")
        except Exception as exc:
            pythoncom.CoUninitialize()
            raise BpacConnectionError(f"{exc}. {_MISSING_HINT}") from exc

        self._doc = document
        self._com_initialized = True

    def close(self) -> None:
        """Close the document and release the COM apartment."""
        try:
            if self._doc is not None:
                self._doc.Close()
        except Exception:
            logger.debug("b-PAC document could not be closed cleanly.", exc_info=True)
        finally:
            self._doc = None

            if self._com_initialized:
                import pythoncom

                pythoncom.CoUninitialize()
                self._com_initialized = False

    def _open(self, path: Path) -> None:
        if not self._doc.Open(str(path)):
            raise LabelTemplateNotFoundError(path)

    def _set_field(self, name: str, value: str) -> None:
        if self._doc is None:
            raise PrinterStateError()

        target = self._doc.GetObject(name)

        if target is None:
            raise LabelFieldNotFoundError(name)

        target.Text = value

    def print(self, copies: int = 1, printer: str = "") -> bool:
        """Submit the document through b-PAC.

        Args:
            copies: Number of copies.
            printer: Printer name. When empty, b-PAC uses the default printer.

        Returns:
            ``True`` when b-PAC accepted the job.
        """
        if self._doc is None:
            raise PrinterStateError()

        if printer:
            self._select_printer(printer)

        self._doc.StartPrint(self._job_name, PrintMode.NORMAL)
        result = self._doc.PrintOut(max(1, copies), PrintMode.NORMAL)

        return bool(result)

    def _select_printer(self, printer: str) -> None:
        set_printer = getattr(self._doc, "SetPrinter", None)

        if set_printer is None:
            logger.warning(
                "This b-PAC version exposes no SetPrinter; printing to the "
                "default printer instead of %r.",
                printer,
            )
            return

        try:
            if not set_printer(printer, ""):
                logger.warning(
                    "b-PAC rejected the printer %r; printing to the default printer.",
                    printer,
                )
        except Exception:
            logger.warning(
                "Selecting printer %r failed; printing to the default printer.",
                printer,
                exc_info=True,
            )


__all__ = ["DEFAULT_JOB_NAME", "BpacDocument"]
