"""Unit tests for the ``.lbx`` parser."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from lbx_printer.lbx.model import BarcodeObject, ImageObject, TextObject
from lbx_printer.lbx.parser import LbxParser

from ..conftest import barcode_object, build_xml, image_object, text_object, write_lbx

pytestmark = pytest.mark.unit


def test_parse_reads_paper_geometry(tmp_path: Path) -> None:
    path = write_lbx(
        tmp_path / "paper.lbx",
        build_xml(
            orientation="landscape",
            auto_length=True,
            width_pt=175.7,
            height_pt=8503.9,
            printer_name="Brother QL-1110NWB",
            format_id=259,
        ),
    )

    paper = LbxParser().parse_file(path).paper

    assert paper.orientation == "landscape"
    assert paper.auto_length is True
    assert paper.width_pt == pytest.approx(175.7)
    assert paper.printer_name == "Brother QL-1110NWB"
    assert paper.format_id == 259
    assert paper.margin_left_pt == pytest.approx(4.3)


def test_parse_reads_text_object_attributes(lbx_factory) -> None:
    path = lbx_factory(
        [
            text_object(
                "address",
                "Ada Lovelace\nLondon",
                x=8.4,
                y=41.3,
                width=65.0,
                height=130.1,
                font="Atlanta",
                size="9.6pt",
                weight=700,
                italic=True,
                h_align="CENTER",
                v_align="BOTTOM",
                shrink=True,
                auto_lf=False,
                line_space=1.5,
                char_space=0.5,
            )
        ]
    )

    layout = LbxParser().parse_file(path)
    obj = layout.get_object("address")

    assert isinstance(obj, TextObject)
    assert obj.text == "Ada Lovelace\nLondon"
    assert obj.x_pt == pytest.approx(8.4)
    assert obj.width_pt == pytest.approx(65.0)
    assert obj.h_align == "CENTER"
    assert obj.v_align == "BOTTOM"
    assert obj.shrink is True
    assert obj.auto_lf is False
    assert obj.line_space == pytest.approx(1.5)
    assert obj.char_space == pytest.approx(0.5)
    assert obj.default_font.name == "Atlanta"
    assert obj.default_font.size_pt == pytest.approx(9.6)
    assert obj.default_font.bold is True
    assert obj.default_font.italic is True


def test_parse_rebuilds_runs_from_string_items(lbx_factory) -> None:
    path = lbx_factory(
        [
            text_object(
                "title",
                "Hello!",
                size="10pt",
                runs=[(5, "10pt"), (1, "16pt")],
            )
        ]
    )

    obj = LbxParser().parse_file(path).get_object("title")

    assert isinstance(obj, TextObject)
    assert [text for text, _ in obj.iter_runs()] == ["Hello", "!"]
    assert obj.runs[1].font.size_pt == pytest.approx(16.0)


def test_parse_falls_back_to_one_run_on_length_mismatch(lbx_factory) -> None:
    path = lbx_factory([text_object("title", "Hello", runs=[(2, "10pt")])])

    obj = LbxParser().parse_file(path).get_object("title")

    assert isinstance(obj, TextObject)
    assert len(obj.runs) == 1
    assert obj.runs[0].length == len("Hello")


def test_parse_keeps_objects_without_name_out_of_the_index(lbx_factory) -> None:
    path = lbx_factory(
        [
            text_object(None, "orphan"),
            text_object("kept", "value"),
        ]
    )

    objects = LbxParser().parse_file(path).objects

    assert list(objects) == ["kept"]


def test_parse_ignores_duplicate_object_names(lbx_factory) -> None:
    path = lbx_factory(
        [
            text_object("title", "first"),
            text_object("title", "second"),
        ]
    )

    obj = LbxParser().parse_file(path).get_object("title")

    assert isinstance(obj, TextObject)
    assert obj.text == "first"


def test_parse_reads_barcode_and_image_objects(lbx_factory) -> None:
    path = lbx_factory([barcode_object("code", "ABC-123"), image_object("logo")])

    objects = LbxParser().parse_file(path).objects

    assert isinstance(objects["code"], BarcodeObject)
    assert objects["code"].value == "ABC-123"
    assert isinstance(objects["logo"], ImageObject)


def test_parse_accepts_open_binary_files(address_lbx: Path) -> None:
    with address_lbx.open("rb") as handle:
        layout = LbxParser().parse(handle)

    assert set(layout.objects) == {"address", "title"}


def test_parse_rejects_archive_without_label_xml(tmp_path: Path) -> None:
    path = write_lbx(tmp_path / "broken.lbx", "<any/>", entry="prop.xml")

    with pytest.raises(ValueError, match=r"label\.xml"):
        LbxParser().parse_file(path)


def test_parse_rejects_non_zip_payload(tmp_path: Path) -> None:
    path = tmp_path / "broken.lbx"
    path.write_bytes(b"not a zip archive")

    with pytest.raises(zipfile.BadZipFile):
        LbxParser().parse_file(path)


def test_parse_rejects_document_without_body(tmp_path: Path) -> None:
    path = write_lbx(
        tmp_path / "broken.lbx",
        '<pt:document xmlns:pt="http://schemas.brother.info/ptouch/2007/lbx/main"/>',
    )

    with pytest.raises(ValueError, match="pt:body"):
        LbxParser().parse_file(path)
