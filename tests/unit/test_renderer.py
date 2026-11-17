"""Unit tests for the renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageOps

from lbx_printer.lbx.fonts import FontResolver
from lbx_printer.lbx.model import FontSpec, LabelLayout, PaperSpec, Run, TextObject
from lbx_printer.lbx.parser import LbxParser
from lbx_printer.lbx.renderer import LbxRenderer, _pt_to_px

from ..conftest import text_object

pytestmark = pytest.mark.unit


def make_text(
    *,
    text: str = "Hello",
    width: float = 100.0,
    height: float = 30.0,
    shrink: bool = False,
    auto_lf: bool = True,
    size_pt: float = 12.0,
) -> TextObject:
    font = FontSpec(name="Arial", size_pt=size_pt)

    return TextObject(
        object_name="title",
        x_pt=0.0,
        y_pt=0.0,
        width_pt=width,
        height_pt=height,
        text=text,
        default_font=font,
        runs=[Run(length=len(text), font=font)],
        shrink=shrink,
        auto_lf=auto_lf,
    )


def make_layout(objects: dict[str, TextObject]) -> LabelLayout:
    return LabelLayout(
        paper=PaperSpec(width_pt=175.7, height_pt=850.3, auto_length=True),
        objects=dict(objects),
    )


def test_render_landscape_continuous_tape_size(address_lbx: Path) -> None:
    layout = LbxParser().parse_file(address_lbx)
    image = LbxRenderer().render(layout)

    assert image.size == (_pt_to_px(175.7, 300), _pt_to_px(82.1, 300))
    assert image.mode == "1"


def test_render_die_cut_keeps_total_paper_size(lbx_factory) -> None:
    path = lbx_factory(
        [text_object("title", "TEST")],
        orientation="portrait",
        auto_length=False,
        width_pt=293.8,
        height_pt=465.8,
    )
    layout = LbxParser().parse_file(path)

    image = LbxRenderer().render(layout)

    assert image.size == (_pt_to_px(293.8, 300), _pt_to_px(465.8, 300))


def ink_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Return the bounding box of the drawn pixels (white is the background)."""
    return ImageOps.invert(image.convert("L")).getbbox()


def test_render_draws_text_inside_the_object_bbox() -> None:
    layout = make_layout({"title": make_text(text="Ink")})
    image = LbxRenderer().render(layout)

    bbox = ink_bbox(image)

    assert bbox is not None, "the rendered label should contain ink"
    assert bbox[2] <= _pt_to_px(100.0, 300)


def test_render_returns_blank_image_for_empty_text() -> None:
    layout = make_layout({"title": make_text(text="")})
    image = LbxRenderer().render(layout)

    assert ink_bbox(image) is None


def test_render_shrinks_long_text_to_the_bounding_box() -> None:
    layout = make_layout(
        {
            "title": make_text(
                text="Supercalifragilistic " * 8,
                width=60,
                height=20,
                shrink=True,
            )
        }
    )

    image = LbxRenderer().render(layout)
    bbox = ink_bbox(image)

    assert bbox is not None
    assert bbox[2] <= _pt_to_px(60.0, 300)
    assert bbox[3] <= _pt_to_px(20.0, 300)


def test_shrink_never_goes_below_the_minimum_size() -> None:
    renderer = LbxRenderer()
    obj = make_text(text="x" * 500, width=10, height=10, shrink=True, size_pt=4.0)
    draw = ImageDraw.Draw(Image.new("L", (10, 10)))

    size = renderer._resolve_font_size(draw, obj.iter_runs(), obj, bbox_w=10, bbox_h=10)

    assert size == pytest.approx(4.0)


def test_wrapping_respects_explicit_newlines_when_auto_lf_is_disabled() -> None:
    renderer = LbxRenderer()
    obj = make_text(text="one\ntwo\nthree", auto_lf=False)
    draw = ImageDraw.Draw(Image.new("L", (10, 10)))

    lines = renderer._wrap_lines(draw, obj.iter_runs(), 12.0, bbox_w=1, obj=obj)

    assert [line for line, _, _ in lines] == ["one", "two", "three"]


def test_wrapping_breaks_long_paragraphs_on_word_boundaries() -> None:
    renderer = LbxRenderer()
    obj = make_text(text="alpha beta gamma delta")
    draw = ImageDraw.Draw(Image.new("L", (10, 10)))

    lines = renderer._wrap_lines(draw, obj.iter_runs(), 12.0, bbox_w=90, obj=obj)

    assert len(lines) > 1
    assert "".join(line for line, _, _ in lines).replace(" ", "").startswith("alpha")


def test_renderer_accepts_a_custom_font_resolver() -> None:
    resolver = FontResolver(substitutions={"Arial": "Arial"})
    renderer = LbxRenderer(font_resolver=resolver, dpi=150)
    image = renderer.render(make_layout({"title": make_text(text="Custom")}))

    assert image.width == _pt_to_px(175.7, 150)


def test_renderer_scales_output_with_dpi() -> None:
    layout = make_layout({"title": make_text()})

    low = LbxRenderer(dpi=150).render(layout)
    high = LbxRenderer(dpi=300).render(layout)

    assert high.width == pytest.approx(low.width * 2, abs=2)
