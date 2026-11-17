"""Shared fixtures and helpers for the test suite."""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "printer"

_NAMESPACES = (
    'xmlns:pt="http://schemas.brother.info/ptouch/2007/lbx/main" '
    'xmlns:style="http://schemas.brother.info/ptouch/2007/lbx/style" '
    'xmlns:text="http://schemas.brother.info/ptouch/2007/lbx/text" '
    'xmlns:draw="http://schemas.brother.info/ptouch/2007/lbx/draw" '
    'xmlns:image="http://schemas.brother.info/ptouch/2007/lbx/image" '
    'xmlns:barcode="http://schemas.brother.info/ptouch/2007/lbx/barcode"'
)


def build_xml(
    objects: Sequence[str] = (),
    *,
    orientation: str = "portrait",
    auto_length: bool = False,
    width_pt: float = 293.8,
    height_pt: float = 465.8,
    margin_left_pt: float = 4.3,
    margin_top_pt: float = 14.3,
    margin_right_pt: float = 4.4,
    margin_bottom_pt: float = 14.3,
    printer_name: str = "",
    format_id: int = 385,
) -> str:
    """Return a complete ``label.xml`` document."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<pt:document {_NAMESPACES} version="1.7">'
        f'<pt:body currentSheet="Sheet 1" direction="LTR">'
        f'<style:sheet name="Sheet 1">'
        f'<style:paper width="{width_pt}pt" height="{height_pt}pt" '
        f'marginLeft="{margin_left_pt}pt" marginTop="{margin_top_pt}pt" '
        f'marginRight="{margin_right_pt}pt" marginBottom="{margin_bottom_pt}pt" '
        f'orientation="{orientation}" autoLength="{str(auto_length).lower()}" '
        f'format="{format_id}" printerName="{printer_name}"/>'
        f"<pt:objects>{''.join(objects)}</pt:objects>"
        f"</style:sheet></pt:body></pt:document>"
    )


def text_object(
    name: str | None,
    text: str,
    *,
    x: float = 8.4,
    y: float = 14.3,
    width: float = 200.0,
    height: float = 50.0,
    font: str = "Arial",
    size: str = "12pt",
    weight: int = 400,
    italic: bool = False,
    h_align: str = "LEFT",
    v_align: str = "TOP",
    shrink: bool = False,
    auto_lf: bool = True,
    line_space: float = 0,
    char_space: float = 0,
    runs: Sequence[tuple[int, str]] = (),
) -> str:
    """Return a ``<text:text>`` element.

    Args:
        name: ``objectName``; ``None`` produces an unaddressable object.
        runs: Optional ``(charLen, size)`` pairs rendered as ``stringItem``.
    """
    expanded = f'<pt:expanded objectName="{name}"/>' if name else ""
    font_info = (
        f'<text:ptFontInfo><text:logFont name="{font}" italic="'
        f'{str(italic).lower()}" weight="{weight}"/>'
        f'<text:fontExt size="{size}" textColor="#000000"/></text:ptFontInfo>'
    )
    items = "".join(
        f'<text:stringItem charLen="{length}"><text:ptFontInfo>'
        f'<text:logFont name="{font}" italic="{str(italic).lower()}" '
        f'weight="{weight}"/>'
        f'<text:fontExt size="{run_size}" textColor="#000000"/></text:ptFontInfo>'
        f"</text:stringItem>"
        for length, run_size in runs
    )

    return (
        f"<text:text>"
        f'<pt:objectStyle x="{x}pt" y="{y}pt" width="{width}pt" '
        f'height="{height}pt" angle="0">{expanded}</pt:objectStyle>'
        f"{font_info}"
        f'<text:textControl shrink="{str(shrink).lower()}" '
        f'autoLF="{str(auto_lf).lower()}"/>'
        f'<text:textAlign horizontalAlignment="{h_align}" '
        f'verticalAlignment="{v_align}"/>'
        f'<text:textStyle lineSpace="{line_space}" charSpace="{char_space}"/>'
        f"<pt:data>{escape(text)}</pt:data>"
        f"{items}"
        f"</text:text>"
    )


def barcode_object(name: str, value: str = "123456") -> str:
    """Return a ``<barcode:barcode>`` element."""
    return (
        f"<barcode:barcode>"
        f'<pt:objectStyle x="10pt" y="10pt" width="100pt" height="40pt">'
        f'<pt:expanded objectName="{name}"/></pt:objectStyle>'
        f"<pt:data>{escape(value)}</pt:data>"
        f"</barcode:barcode>"
    )


def image_object(name: str) -> str:
    """Return an ``<image:image>`` element."""
    return (
        f"<image:image>"
        f'<pt:objectStyle x="20pt" y="20pt" width="50pt" height="50pt">'
        f'<pt:expanded objectName="{name}"/></pt:objectStyle>'
        f"</image:image>"
    )


def write_lbx(target: Path, xml: str, entry: str = "label.xml") -> Path:
    """Write ``xml`` into a ``.lbx`` archive and return its path."""
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(entry, xml)

    return target


@pytest.fixture
def address_lbx() -> Path:
    """Fixture template with an ``address`` and a ``title`` field."""
    path = FIXTURES_DIR / "address.lbx"

    if not path.is_file():
        pytest.skip(f"Missing test fixture: {path}")

    return path


@pytest.fixture
def lbx_factory(tmp_path: Path):
    """Return a callable that writes a synthesised ``.lbx`` file."""

    def factory(
        objects: Sequence[str] = (),
        name: str = "template.lbx",
        **paper: object,
    ) -> Path:
        xml = build_xml(objects, **paper)  # type: ignore[arg-type]
        return write_lbx(tmp_path / name, xml)

    return factory
