"""Unit tests for the font resolver."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from PIL import ImageFont

from lbx_printer.lbx.fonts import DEFAULT_SUBSTITUTIONS, FontResolver, _normalize

pytestmark = pytest.mark.unit


def system_font_files() -> list[Path]:
    if sys.platform.startswith("win"):
        import os

        root = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

        return sorted(root.glob("*.ttf"))

    return sorted(Path("/usr/share/fonts").rglob("*.ttf"))


def test_substitutions_cover_brother_font_families() -> None:
    for family in ("Atlanta", "Letter Gothic", "US Roman"):
        assert family in DEFAULT_SUBSTITUTIONS


def test_resolve_returns_a_free_type_font() -> None:
    font = FontResolver().resolve("Atlanta", size_px=24)

    assert isinstance(font, ImageFont.FreeTypeFont)
    assert font.size == 24


def test_resolve_is_cached() -> None:
    resolver = FontResolver()

    first = resolver.resolve("Arial", bold=True, size_px=12)
    second = resolver.resolve("Arial", bold=True, size_px=12)

    assert first is second


def test_resolve_is_case_and_separator_insensitive() -> None:
    resolver = FontResolver()

    assert resolver.resolve("ATLANTA", size_px=10) is resolver.resolve(
        "atlanta", size_px=10
    )
    assert _normalize("DejaVu Sans") == _normalize("dejavusans")


def test_unknown_font_falls_back_instead_of_failing() -> None:
    font = FontResolver().resolve("No Such Font Family 42", size_px=18)

    assert isinstance(font, ImageFont.FreeTypeFont)


def test_extra_directories_are_indexed(tmp_path: Path) -> None:
    candidates = system_font_files()

    if not candidates:
        pytest.skip("No TrueType font available on this machine")

    custom = tmp_path / "fonts"
    custom.mkdir()
    shutil.copy2(candidates[0], custom / "MyCustomFace.ttf")

    font = FontResolver(extra_dirs=[custom]).resolve("MyCustomFace", size_px=20)

    assert isinstance(font, ImageFont.FreeTypeFont)
    assert font.path is not None
    assert Path(str(font.path)).parent == custom


def test_available_families_is_not_empty_when_fonts_exist() -> None:
    if not system_font_files():
        pytest.skip("No TrueType font available on this machine")

    assert FontResolver().available_families()
