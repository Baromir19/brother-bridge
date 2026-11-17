"""Integration tests for the end-to-end label pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageOps

from lbx_printer import (
    FileBackend,
    LabelData,
    LabelPrinterService,
    LabelTemplate,
    LabelTemplateService,
    LbxParser,
    LbxRenderer,
    PrintRequest,
)
from lbx_printer.exceptions import LabelFieldNotFoundError
from lbx_printer.managers import document_factory

pytestmark = pytest.mark.integration


def test_parse_render_and_write_files(address_lbx: Path, tmp_path: Path) -> None:
    layout = LbxParser().parse_file(address_lbx)
    layout.text_objects["title"].set_text("Ada Lovelace")
    layout.text_objects["address"].set_text("12 rue de la Paix\n75002 Paris")

    image = LbxRenderer().render(layout)
    backend = FileBackend(tmp_path / "output", prefix="address")

    assert backend.print(image, printer="", copies=2) is True

    written = sorted((tmp_path / "output").glob("address_*.png"))
    assert len(written) == 2

    with Image.open(written[0]) as saved:
        assert saved.size == image.size
        assert ImageOps.invert(saved.convert("L")).getbbox() is not None


def test_service_prints_through_the_posix_document(
    address_lbx: Path, tmp_path: Path
) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "address.lbx").write_bytes(address_lbx.read_bytes())

    backend = FileBackend(tmp_path / "output")
    service = LabelPrinterService(
        templates,
        document_factory=lambda: document_factory(
            backend=backend, platform_name="Linux"
        ),
    )
    request = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "Grace Hopper", "address": "Arlington"}),
        copies=1,
    )

    assert service.print_label(request) is True
    assert list((tmp_path / "output").glob("label_*.png"))


def test_rendered_width_matches_the_tape_geometry(address_lbx: Path) -> None:
    layout = LbxParser().parse_file(address_lbx)
    image = LbxRenderer().render(layout)

    assert layout.paper.width_mm == 62
    assert image.width == round(62 * 300 / 25.4)


def test_template_service_and_printer_service_share_field_names(
    address_lbx: Path, tmp_path: Path
) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    service = LabelTemplateService(templates)
    template = service.import_file(address_lbx, name="address")

    assert template.fields == ("address", "title")

    layout = LbxParser().parse_file(templates / template.template)
    assert set(template.fields) == set(layout.text_objects)


def test_injected_values_reach_the_printed_image(
    address_lbx: Path, tmp_path: Path
) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "address.lbx").write_bytes(address_lbx.read_bytes())

    backend = FileBackend(tmp_path / "output")
    service = LabelPrinterService(
        templates,
        document_factory=lambda: document_factory(
            backend=backend, platform_name="Linux"
        ),
    )
    blank = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "", "address": ""}),
    )
    filled = PrintRequest(
        label=LabelTemplate("address", "address.lbx", ("title", "address")),
        data=LabelData({"title": "Ada Lovelace", "address": "London"}),
    )

    assert service.print_label(blank) is True
    assert service.print_label(filled) is True

    images = sorted((tmp_path / "output").glob("label_*.png"))
    assert len(images) == 2

    with Image.open(images[0]) as first, Image.open(images[1]) as second:
        assert ImageOps.invert(first.convert("L")).getbbox() is None
        assert ImageOps.invert(second.convert("L")).getbbox() is not None


def test_layout_lookup_reports_unknown_fields(address_lbx: Path) -> None:
    layout = LbxParser().parse_file(address_lbx)

    with pytest.raises(LabelFieldNotFoundError):
        layout.get_object("unknown")
