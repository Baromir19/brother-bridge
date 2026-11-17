"""Unit tests for the document managers and the factory."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from brother_bridge.config import PrinterConfig
from brother_bridge.exceptions import (
    LabelFieldNotFoundError,
    LabelTemplateNotFoundError,
    PrinterStateError,
)
from brother_bridge.lbx.parser import LbxParser
from brother_bridge.managers import LabelDocument, document_factory
from brother_bridge.managers.bpac_document import BpacDocument
from brother_bridge.managers.linux_brother_document import (
    LinuxBrotherDocument,
    TapeSpec,
    default_tape_spec,
)
from brother_bridge.printers.backend import PrinterBackend

from ..conftest import image_object, text_object

pytestmark = pytest.mark.unit


class RecordingBackend(PrinterBackend):
    """Capture the image and job parameters instead of printing."""

    def __init__(self) -> None:
        self.image: Image.Image | None = None
        self.printer = ""
        self.copies = 0

    def print(self, image: Image.Image, printer: str, copies: int = 1) -> bool:
        self.image = image
        self.printer = printer
        self.copies = copies

        return True


def linux_document(backend: PrinterBackend) -> LinuxBrotherDocument:
    return LinuxBrotherDocument(
        backend=backend,
        tape_spec_provider=lambda _: TapeSpec((696, 200), die_cut=False),
    )


def test_open_rejects_a_missing_template() -> None:
    with pytest.raises(LabelTemplateNotFoundError):
        linux_document(RecordingBackend()).open(Path("does-not-exist.lbx"))


def test_fields_can_only_be_set_after_open(address_lbx: Path) -> None:
    with pytest.raises(PrinterStateError):
        linux_document(RecordingBackend()).set_field("title", "x")


def test_print_requires_an_open_document() -> None:
    with pytest.raises(PrinterStateError):
        linux_document(RecordingBackend()).print()


def test_unknown_field_is_reported(address_lbx: Path) -> None:
    document = linux_document(RecordingBackend())

    with document:
        document.open(address_lbx)

        with pytest.raises(LabelFieldNotFoundError):
            document.set_field("missing", "value")


def test_non_text_field_is_rejected(lbx_factory) -> None:
    path = lbx_factory([image_object("logo"), text_object("title", "x")])
    document = linux_document(RecordingBackend())

    with document:
        document.open(path)

        with pytest.raises(TypeError, match="logo"):
            document.set_field("logo", "value")


def test_pipeline_renders_and_forwards_the_job(address_lbx: Path) -> None:
    backend = RecordingBackend()
    document = linux_document(backend)

    with document:
        document.open(address_lbx)
        document.set_fields({"title": "Ada Lovelace", "address": "London"})

        assert document.resolved_label == "62"
        assert document.print(copies=2, printer="queue-a") is True

    assert backend.copies == 2
    assert backend.printer == "queue-a"
    assert backend.image is not None
    assert backend.image.mode == "L"


def test_template_printer_is_used_when_none_is_given(lbx_factory) -> None:
    backend = RecordingBackend()
    path = lbx_factory(
        [text_object("title", "x")],
        orientation="landscape",
        auto_length=True,
        width_pt=175.7,
        height_pt=850.3,
        printer_name="Brother QL-1110NWB",
    )
    document = linux_document(backend)

    with document:
        document.open(path)
        document.print()

    assert backend.printer == "Brother QL-1110NWB"


def test_die_cut_labels_are_cropped_to_the_printable_area(lbx_factory) -> None:
    backend = RecordingBackend()
    path = lbx_factory([text_object("title", "TEST")], width_pt=293.8, height_pt=465.8)
    document = LinuxBrotherDocument(
        backend=backend,
        tape_spec_provider=lambda _: TapeSpec((1200, 1822), die_cut=True),
    )

    with document:
        document.open(path)
        document.print()

    assert backend.image is not None
    assert backend.image.size == (1200, 1822)


def test_crop_is_skipped_when_the_image_is_smaller_than_the_label(lbx_factory) -> None:
    backend = RecordingBackend()
    path = lbx_factory([text_object("title", "TEST")], width_pt=293.8, height_pt=465.8)
    document = LinuxBrotherDocument(
        backend=backend,
        tape_spec_provider=lambda _: TapeSpec((4000, 4000), die_cut=True),
    )

    with document:
        document.open(path)
        document.print()

    assert backend.image is not None
    assert backend.image.size == (1224, 1941)


def test_label_override_bypasses_geometry_resolution(address_lbx: Path) -> None:
    document = LinuxBrotherDocument(
        backend=RecordingBackend(),
        label="62",
        tape_spec_provider=lambda _: TapeSpec((696, 200), die_cut=False),
    )

    with document:
        document.open(address_lbx)

        assert document.resolved_label == "62"


def test_default_tape_spec_comes_from_brother_ql() -> None:
    spec = default_tape_spec("103x164")

    assert spec.dots_printable == (1200, 1822)
    assert spec.die_cut is True


def test_default_tape_spec_is_cached() -> None:
    assert default_tape_spec("62") is default_tape_spec("62")


def test_factory_selects_the_windows_document() -> None:
    document = document_factory(platform_name="Windows")

    assert isinstance(document, BpacDocument)
    assert isinstance(document, LabelDocument)


def test_factory_selects_the_posix_document_with_configuration() -> None:
    backend = RecordingBackend()
    config = PrinterConfig(host="192.0.2.10", model="QL-800", label="29", dpi=150)

    document = document_factory(config, backend=backend, platform_name="Linux")

    assert isinstance(document, LinuxBrotherDocument)
    assert document.host == "192.0.2.10"
    assert document.model == "QL-800"


def test_bpac_document_requires_initialisation() -> None:
    with pytest.raises(PrinterStateError):
        BpacDocument().print()


def test_bpac_field_update_requires_initialisation() -> None:
    with pytest.raises(PrinterStateError):
        BpacDocument().set_field("title", "x")


def test_parser_layout_and_document_agree_on_field_names(address_lbx: Path) -> None:
    layout = LbxParser().parse_file(address_lbx)

    assert set(layout.text_objects) == {"address", "title"}
