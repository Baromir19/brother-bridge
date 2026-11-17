"""Unit tests for the printing service."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from lbx_printer.exceptions import (
    LabelDataMissingError,
    LabelTemplateNotFoundError,
    PrinterStateError,
)
from lbx_printer.managers.label_document import LabelDocument
from lbx_printer.models import LabelData, LabelTemplate, PrintRequest
from lbx_printer.services import LabelPrinterService

pytestmark = pytest.mark.unit


class FakeDocument(LabelDocument):
    """In-memory document that records every call."""

    instances: ClassVar[list[FakeDocument]] = []

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.opened: Path | None = None
        self.fields: dict[str, str] = {}
        self.copies = 0
        self.printer = ""
        self.closed = False
        FakeDocument.instances.append(self)

    def _open(self, path: Path) -> None:
        self.opened = path
        self.calls.append(("open", path))

    def _set_field(self, name: str, value: str) -> None:
        self.fields[name] = value
        self.calls.append(("set_field", (name, value)))

    def print(self, copies: int = 1, printer: str = "") -> bool:
        self.copies = copies
        self.printer = printer
        self.calls.append(("print", (copies, printer)))

        return True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def service(tmp_path: Path, address_lbx: Path) -> LabelPrinterService:
    target = tmp_path / "templates"
    target.mkdir()
    (target / address_lbx.name).write_bytes(address_lbx.read_bytes())
    FakeDocument.instances.clear()

    return LabelPrinterService(target, document_factory=FakeDocument)


def test_service_prints_a_complete_request(service: LabelPrinterService) -> None:
    request = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "Ada", "address": "London"}),
        copies=3,
        printer="queue-b",
    )

    assert service.print_label(request) is True

    document = FakeDocument.instances[-1]
    assert document.opened == service.template_dir / "address.lbx"
    assert document.fields == {"title": "Ada", "address": "London"}
    assert document.copies == 3
    assert document.printer == "queue-b"
    assert document.closed is True
    assert document.calls[0][0] == "open"
    assert document.calls[-1][0] == "print"


def test_service_rejects_missing_templates(service: LabelPrinterService) -> None:
    request = PrintRequest(
        label=LabelTemplate("missing", "missing.lbx", ()),
        data=LabelData(),
    )

    with pytest.raises(LabelTemplateNotFoundError):
        service.print_label(request)


def test_service_rejects_missing_field_values(service: LabelPrinterService) -> None:
    request = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "Ada"}),
    )

    with pytest.raises(LabelDataMissingError) as excinfo:
        service.print_label(request)

    assert excinfo.value.fields == ("address",)


def test_service_closes_the_document_on_errors(service: LabelPrinterService) -> None:
    request = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title",)),
        data=LabelData({"title": "Ada"}),
    )

    original = FakeDocument._set_field

    def failing_set_field(self: FakeDocument, name: str, value: str) -> None:
        raise PrinterStateError("boom")

    FakeDocument._set_field = failing_set_field  # type: ignore[method-assign]

    try:
        with pytest.raises(PrinterStateError):
            service.print_label(request)
    finally:
        FakeDocument._set_field = original  # type: ignore[method-assign]

    assert FakeDocument.instances[-1].closed is True
