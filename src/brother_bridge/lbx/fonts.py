"""Font resolution for the label renderer.

Brother templates reference font families such as ``Atlanta`` or
``Letter Gothic`` that exist only on Windows installations of P-touch Editor.
:class:`FontResolver` maps those names onto fonts that are actually available:

1. exact family match in the system font directories,
2. a configurable substitution table (Brother family to candidates),
3. a partial match against the indexed family names,
4. a font shipped in ``brother_bridge/resources/fonts``,
5. the scalable default font of Pillow.

Resolved fonts are cached per ``(family, bold, italic, size)`` so that repeated
renders do not hit the disk. The resolver is thread-safe.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from PIL import ImageFont

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_RESOURCES_FONTS_DIR = _PACKAGE_ROOT / "resources" / "fonts"
_FALLBACK_FONT_NAMES = ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")

_FONT_SUFFIXES = frozenset({".ttf", ".otf"})

_SANS_FAMILIES: tuple[str, ...] = (
    "DejaVu Sans",
    "Liberation Sans",
    "Arial",
    "Helvetica",
)
_MONO_FAMILIES: tuple[str, ...] = (
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Courier New",
)


def _platform_families(
    sans: tuple[str, ...], mono: tuple[str, ...]
) -> dict[str, tuple[str, ...]]:
    """Build the substitution table for the current platform."""
    if sys.platform.startswith("win"):
        sans = ("Arial", "Helvetica", "Liberation Sans", "DejaVu Sans")
        mono = ("Consolas", "Courier New", "Liberation Mono", "DejaVu Sans Mono")
    elif sys.platform == "darwin":
        sans = (
            "Helvetica Neue",
            "Helvetica",
            "Arial",
            "Liberation Sans",
            "DejaVu Sans",
        )
        mono = ("Menlo", "Courier New", "Liberation Mono", "DejaVu Sans Mono")

    return {
        "Atlanta": sans,
        "Brussels": sans,
        "Helsinki": sans,
        "Los Angeles": sans,
        "San Diego": sans,
        "Tahoma": sans,
        "US Roman": sans,
        "Letter Gothic": mono,
    }


DEFAULT_SUBSTITUTIONS: dict[str, tuple[str, ...]] = _platform_families(
    _SANS_FAMILIES, _MONO_FAMILIES
)
"""Brother families mapped to candidate families, ordered by platform."""


def _system_font_dirs() -> list[Path]:
    """Return the font directories to scan on the current platform."""
    if sys.platform.startswith("win"):
        import os

        dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
        local_app_data = os.environ.get("LOCALAPPDATA")

        if local_app_data:
            dirs.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")

        return dirs

    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local" / "share" / "fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path.home() / "Library" / "Fonts",
    ]


def _normalize(name: str) -> str:
    """Normalise a family name for case- and separator-insensitive matching."""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


_STYLE_KEYWORDS = (
    "bold",
    "italic",
    "oblique",
    "light",
    "medium",
    "black",
    "heavy",
    "thin",
    "semibold",
    "extrabold",
    "condensed",
    "narrow",
)


def _regularity(path: Path, family: str | None) -> int:
    """Rank how close a font file is to the regular face of its family.

    Lower is better: ``0`` for an exact regular file name, ``1`` for a variant
    without a style keyword, ``2`` for anything else.
    """
    if not family:
        return 2

    stem = _normalize(path.stem)
    normalized_family = _normalize(family)

    if stem == normalized_family:
        return 0

    if stem.startswith(normalized_family):
        remainder = stem[len(normalized_family) :]

        if not any(keyword in remainder for keyword in _STYLE_KEYWORDS):
            return 1

    return 2


def _read_family_name(path: Path) -> str | None:
    """Read the family name (nameID 1) of a font file, if fontTools is present."""
    try:
        from fontTools.ttLib import TTFont

        with TTFont(str(path), lazy=True) as font:
            name_table = font["name"]

            for record in name_table.names:
                if record.nameID == 1 and record.platformID in (1, 3):
                    return cast(str, record.toUnicode())

    except Exception as exc:  # fontTools missing or the file is not readable
        logger.debug("Cannot read the family name of %s: %s", path, exc)

    return None


def _scan_fonts(extra_dirs: Sequence[Path] = ()) -> dict[str, Path]:
    """Index the available font files by normalised family and file stem.

    Args:
        extra_dirs: Additional directories to scan before system directories.

    Returns:
        Mapping from normalised family name (and file stem) to font file. When
        several files share a family, the one closest to the regular face wins,
        so a family is never represented by an arbitrary bold or italic file.
    """
    index: dict[str, Path] = {}
    priority: dict[str, int] = {}

    for directory in [*extra_dirs, *_system_font_dirs(), _RESOURCES_FONTS_DIR]:
        if not directory.is_dir():
            continue

        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in _FONT_SUFFIXES:
                continue

            family = _read_family_name(path)
            keys = {_normalize(path.stem)}

            if family:
                keys.add(_normalize(family))

            score = _regularity(path, family)

            for key in keys:
                current = priority.get(key)

                if current is None or score < current:
                    index[key] = path
                    priority[key] = score

    logger.debug("Font index built with %d entries.", len(index))

    return index


class FontResolver:
    """Resolve template font names to Pillow fonts.

    Args:
        substitutions: Custom Brother-to-candidate mapping. Values may be a
            single family name or a sequence of candidates tried in order.
            Defaults to :data:`DEFAULT_SUBSTITUTIONS`.
        extra_dirs: Additional font directories, scanned before system ones.

    Example:
        >>> resolver = FontResolver(extra_dirs=[Path("assets/fonts")])
        >>> font = resolver.resolve("Atlanta", size_px=32)
    """

    def __init__(
        self,
        substitutions: Mapping[str, str | Sequence[str]] | None = None,
        extra_dirs: Sequence[Path] | None = None,
    ) -> None:
        source = DEFAULT_SUBSTITUTIONS if substitutions is None else substitutions

        self._substitutions: dict[str, tuple[str, ...]] = {
            _normalize(name): (value,) if isinstance(value, str) else tuple(value)
            for name, value in source.items()
        }
        self._extra_dirs = tuple(Path(directory) for directory in extra_dirs or ())
        self._font_index: dict[str, Path] | None = None
        self._cache: dict[tuple[str, bool, bool, int], ImageFont.FreeTypeFont] = {}
        self._index_lock = threading.Lock()
        self._cache_lock = threading.Lock()

    def available_families(self) -> tuple[str, ...]:
        """Return the normalised family names found on this machine."""
        return tuple(sorted(self._index()))

    def resolve(
        self,
        name: str,
        bold: bool = False,
        italic: bool = False,
        size_px: int = 12,
    ) -> ImageFont.FreeTypeFont:
        """Return a Pillow font for the requested style.

        Args:
            name: Font family used by the template, e.g. ``"Atlanta"``.
            bold: Request a bold variant when one is available.
            italic: Request an italic variant when one is available.
            size_px: Size in pixels, already converted from points.

        Returns:
            A ready-to-use font. Resolution never fails: the Pillow default font
            is returned when nothing else matches.
        """
        key = (_normalize(name), bold, italic, size_px)

        with self._cache_lock:
            cached = self._cache.get(key)

        if cached is not None:
            return cached

        font = self._load_font(name, bold, italic, size_px)

        with self._cache_lock:
            self._cache.setdefault(key, font)

        return font

    def _index(self) -> dict[str, Path]:
        if self._font_index is None:
            with self._index_lock:
                if self._font_index is None:
                    self._font_index = _scan_fonts(self._extra_dirs)

        return self._font_index

    def _load_font(
        self,
        name: str,
        bold: bool,
        italic: bool,
        size_px: int,
    ) -> ImageFont.FreeTypeFont:
        path = (
            self._find_exact(name, bold, italic)
            or self._find_by_substitution(name, bold, italic)
            or self._find_partial(name, bold, italic)
            or self._fallback_font_path()
        )

        if path is None:
            logger.warning("No font found for %r; using the Pillow default font.", name)
            return self._default_font(size_px)

        try:
            return ImageFont.truetype(str(path), size=size_px)
        except OSError as exc:
            logger.warning(
                "Cannot load font %s: %s; using the default font.", path, exc
            )
            return self._default_font(size_px)

    @staticmethod
    def _default_font(size_px: int) -> ImageFont.FreeTypeFont:
        try:
            return cast(ImageFont.FreeTypeFont, ImageFont.load_default(size=size_px))
        except TypeError:  # Pillow < 10.1 has no scalable default font
            return cast(ImageFont.FreeTypeFont, ImageFont.load_default())

    def _find_exact(
        self,
        family: str,
        bold: bool,
        italic: bool,
    ) -> Path | None:
        base = self._index().get(_normalize(family))

        if base is None:
            return None

        styled = self._find_style_variant(base.parent, family, bold, italic)

        return styled or base

    def _find_by_substitution(
        self,
        family: str,
        bold: bool,
        italic: bool,
    ) -> Path | None:
        candidates = self._substitutions.get(_normalize(family))

        if not candidates:
            return None

        for candidate in candidates:
            path = self._find_exact(candidate, bold, italic)

            if path is not None:
                logger.debug("Font substitution: %r -> %r", family, candidate)
                return path

            path = self._find_partial(candidate, bold, italic)

            if path is not None:
                logger.debug("Font substitution (partial): %r -> %r", family, candidate)
                return path

        return None

    def _find_partial(
        self,
        family: str,
        bold: bool,
        italic: bool,
    ) -> Path | None:
        needle = _normalize(family)

        for key, path in self._index().items():
            if needle and needle in key:
                styled = self._find_style_variant(path.parent, key, bold, italic)
                logger.debug("Partial font match for %r: %s", family, path)

                return styled or path

        return None

    @staticmethod
    def _find_style_variant(
        directory: Path,
        family: str,
        bold: bool,
        italic: bool,
    ) -> Path | None:
        suffixes: list[str] = []

        if bold and italic:
            suffixes += ["BoldItalic", "BoldOblique", "Bold-Italic"]
        elif bold:
            suffixes += ["Bold"]
        elif italic:
            suffixes += ["Italic", "Oblique"]

        if not suffixes:
            return None

        normalized_family = _normalize(family)

        for suffix in suffixes:
            normalized_suffix = _normalize(suffix)

            for path in sorted(directory.glob("*")):
                if path.suffix.lower() not in _FONT_SUFFIXES:
                    continue

                stem = _normalize(path.stem)

                if normalized_family in stem and normalized_suffix in stem:
                    return path

        return None

    @staticmethod
    def _fallback_font_path() -> Path | None:
        for name in _FALLBACK_FONT_NAMES:
            path = _RESOURCES_FONTS_DIR / name

            if path.is_file():
                return path

        return None


__all__ = ["DEFAULT_SUBSTITUTIONS", "FontResolver"]
