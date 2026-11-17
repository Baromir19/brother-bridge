"""Unit tests for the ``LbxUtils`` helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from lbx_printer.utils import LbxUtils

from ..conftest import barcode_object, image_object, text_object

pytestmark = pytest.mark.unit


def test_extract_fields_returns_every_named_object(lbx_factory) -> None:
    path = lbx_factory(
        [
            text_object("title", "x"),
            image_object("logo"),
            barcode_object("code"),
        ]
    )

    assert LbxUtils.extract_fields(path) == ["title", "logo", "code"]


def test_extract_fields_can_restrict_to_text_objects(lbx_factory) -> None:
    path = lbx_factory([text_object("title", "x"), image_object("logo")])

    assert LbxUtils.extract_fields(path, text_only=True) == ["title"]


def test_read_paper(address_lbx: Path) -> None:
    paper = LbxUtils.read_paper(address_lbx)

    assert paper.orientation == "landscape"
    assert paper.width_mm == 62
