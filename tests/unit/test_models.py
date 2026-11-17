"""Unit tests for the public data models."""

from __future__ import annotations

import dataclasses

import pytest

from lbx_printer import __version__
from lbx_printer.exceptions import (
    ConfigurationError,
    LabelFieldNotFoundError,
    LabelTemplateNotFoundError,
)
from lbx_printer.lbx.model import FontSpec, LabelLayout, PaperSpec, Run, TextObject
from lbx_printer.models import LabelData, LabelTemplate, PrintMode, PrintRequest

pytestmark = pytest.mark.unit


def make_layout() -> LabelLayout:
    font = FontSpec(name="Arial", size_pt=12.0)
    text = TextObject(
        object_name="title",
        x_pt=0.0,
        y_pt=0.0,
        width_pt=100.0,
        height_pt=20.0,
        text="Hello world",
        default_font=font,
        runs=[Run(length=5, font=font), Run(length=6, font=font)],
    )

    return LabelLayout(
        paper=PaperSpec(width_pt=175.7, height_pt=850.3, auto_length=True),
        objects={"title": text},
    )


def test_public_version_is_declared() -> None:
    assert __version__.count(".") >= 1


def test_label_data_behaves_like_a_mapping() -> None:
    data = LabelData({"title": "Ada", "copies": "3"})

    assert data["copies"] == "3"
    assert "title" in data
    assert len(data) == 2
    assert sorted(data) == ["copies", "title"]
    assert data.get("missing") is None
    assert data.as_dict() == {"title": "Ada", "copies": "3"}


def test_label_data_defaults_to_empty() -> None:
    assert LabelData().as_dict() == {}


def test_label_template_is_immutable_and_resolves_paths(tmp_path) -> None:
    template = LabelTemplate("address", "address.lbx", ("title",))

    assert template.fields == ("title",)

    with pytest.raises(dataclasses.FrozenInstanceError):
        template.name = "other"  # type: ignore[misc]

    with pytest.raises(LabelTemplateNotFoundError):
        template.resolve(tmp_path)

    (tmp_path / "address.lbx").write_bytes(b"stub")
    assert template.resolve(tmp_path) == tmp_path / "address.lbx"


def test_print_request_validates_copies() -> None:
    with pytest.raises(ConfigurationError):
        PrintRequest(LabelTemplate("t", "t.lbx"), LabelData(), copies=0)


def test_print_request_reports_missing_fields() -> None:
    request = PrintRequest(
        label=LabelTemplate("t", "t.lbx", ("a", "b")),
        data=LabelData({"a": "1"}),
        printer="  queue  ",
    )

    assert request.missing_fields() == ("b",)
    assert request.printer == "queue"


def test_print_mode_values_match_bpac_defaults() -> None:
    assert int(PrintMode.NORMAL) == 0


def test_text_object_replaces_runs_on_set_text() -> None:
    layout = make_layout()
    obj = layout.get_object("title")
    assert isinstance(obj, TextObject)
    assert [text for text, _ in obj.iter_runs()] == ["Hello", " world"]

    obj.set_text("New")

    assert obj.text == "New"
    assert obj.runs == [Run(length=3, font=obj.default_font)]
    assert obj.iter_runs() == [("New", obj.default_font)]


def test_layout_lookup_uses_template_object_names() -> None:
    layout = make_layout()

    assert set(layout.text_objects) == {"title"}

    with pytest.raises(LabelFieldNotFoundError):
        layout.get_object("address")


def test_paper_spec_converts_points_to_millimetres() -> None:
    paper = PaperSpec(width_pt=175.7, height_pt=465.8, auto_length=False)

    assert paper.exact_width_mm == pytest.approx(61.98, abs=0.01)
    assert paper.width_mm == 62
    assert paper.height_mm == 164


def test_paper_spec_height_is_none_for_continuous_tape() -> None:
    paper = PaperSpec(width_pt=175.7, height_pt=0.0, auto_length=True)

    assert paper.exact_height_mm is None
    assert paper.height_mm is None
