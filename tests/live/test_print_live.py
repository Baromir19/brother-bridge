"""Live tests that talk to a real printer.

These tests are excluded by default. Run them explicitly with hardware
available::

    LBX_PRINTER_HOST=192.168.1.50 pytest -m live

On Windows the tests use b-PAC; on Linux and macOS they stream raster data to
the address above. Nothing is printed when the environment variable is unset.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lbx_printer import (
    LabelData,
    LabelPrinterService,
    LabelTemplate,
    PrintRequest,
)

pytestmark = pytest.mark.live

HOST = os.environ.get("LBX_PRINTER_HOST", "")
MODEL = os.environ.get("LBX_PRINTER_MODEL", "QL-1110NWB")


def live_template(address_lbx: Path) -> LabelTemplate:
    return LabelTemplate(
        name="address",
        template=address_lbx.name,
        fields=("title", "address"),
    )


@pytest.mark.skipif(not HOST, reason="LBX_PRINTER_HOST is not set")
def test_print_label_on_hardware(address_lbx: Path) -> None:
    from lbx_printer.config import PrinterConfig
    from lbx_printer.managers import document_factory

    request = PrintRequest(
        label=live_template(address_lbx),
        data=LabelData(
            {
                "title": "lbx-printer",
                "address": "Live hardware test label",
            }
        ),
        copies=1,
    )
    service = LabelPrinterService(
        address_lbx.parent,
        document_factory=lambda: document_factory(
            PrinterConfig(host=HOST, model=MODEL)
        ),
    )

    assert service.print_label(request) is True
