"""
Résolution de polices pour le renderer d'étiquettes Brother.

Stratégie de recherche pour un nom de police donné (ex. ``"Atlanta"``) :

1. Correspondance exacte dans les répertoires système standard
   (``/usr/share/fonts``, ``/usr/local/share/fonts``, ``~/.fonts``,
   ``~/.local/share/fonts``).
2. Correspondance partielle (le nom de famille figure dans le nom du fichier
   TTF/OTF) - utile pour les variantes ``-Regular``, ``-Bold``, etc.
3. Mappe de substitution configurable
   (ex. ``{"Atlanta": "DejaVuSans"}``).
4. Fallback absolu : ``resources/fonts/DejaVuSans.ttf`` embarqué dans
   le projet.

La résolution est mise en cache par ``(nom, gras, italique, taille_px)``
pour éviter les lectures disque répétées lors du rendu de multiples runs.

Note sur fonttools
------------------
``fonttools`` est utilisé uniquement pour lire les métadonnées des fichiers
TTF lors du scan initial (nom de famille réel). PIL/Pillow est utilisé pour
créer les objets ``ImageFont`` à partir des chemins résolus.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from PIL import ImageFont

from config.paths import RESOURCES_DIR

logger = logging.getLogger(__name__)

_SYSTEM_FONT_DIRS: list[Path] = [
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local" / "share" / "fonts",
    # macOS
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path.home() / "Library" / "Fonts",
]

# Répertoire des polices embarquées (fallback)
_RESOURCES_FONTS_DIR: Path = RESOURCES_DIR / "fonts"

_FALLBACK_FONT_NAME = "DejaVuSans.ttf"

#: Mappe ``nom_brother -> nom_partiel_fichier`` pour les polices propriétaires
#: Brother qui n'existent pas sur Linux.
DEFAULT_SUBSTITUTIONS: dict[str, str] = {
    "Atlanta": "DejaVuSans",
    "Helsinki": "DejaVuSans",
    "Brussels": "DejaVuSans",
    "San Diego": "DejaVuSans",
    "Los Angeles": "DejaVuSans",
    "Letter Gothic": "DejaVuSansMono",
    "US Roman": "DejaVuSans",
    "Tahoma": "DejaVuSans",
}


def _scan_fonts() -> dict[str, Path]:
    """
    Scanne les répertoires système et retourne un dictionnaire
    ``{nom_famille_lower: chemin_ttf}``.

    La détection du nom de famille utilise ``fonttools`` si disponible,
    sinon elle tombe sur le nom du fichier (sans extension).

    Returns:
        Dictionnaire indexé par nom de famille en minuscules.
    """
    index: dict[str, Path] = {}

    try:
        use_fonttools = True
    except ImportError:
        logger.debug(
            "fonttools non disponible - indexation par nom de fichier uniquement."
        )
        use_fonttools = False

    dirs_to_scan = _SYSTEM_FONT_DIRS + [_RESOURCES_FONTS_DIR]

    for font_dir in dirs_to_scan:
        if not font_dir.exists():
            continue

        for path in font_dir.rglob("*"):
            if path.suffix.lower() not in {".ttf", ".otf"}:
                continue

            if use_fonttools:
                family = _read_family_name(path)
            else:
                family = path.stem

            if family:
                key = family.lower()
                # Priorité aux polices système sur les embarquées
                if key not in index:
                    index[key] = path

    logger.debug("Index de polices construit : %d familles trouvées.", len(index))
    return index


def _read_family_name(path: Path) -> str | None:
    """
    Lit le nom de famille (nameID=1) d'un fichier TTF/OTF via fonttools.

    Args:
        path: Chemin vers le fichier de police.

    Returns:
        Nom de famille, ou ``None`` en cas d'erreur de lecture.
    """
    try:
        from fontTools.ttLib import TTFont

        tt = TTFont(str(path), lazy=True)
        name_table = tt["name"]

        # nameID 1 = Family name, platformID 3 = Windows, 1 = Mac/Unicode
        for record in name_table.names:
            if record.nameID == 1 and record.platformID in (1, 3):
                return cast(str, record.toUnicode())

    except Exception as exc:
        logger.debug("Impossible de lire la police %s : %s", path, exc)

    return None


class FontResolver:
    """
    Résolveur de polices TTF pour le renderer d'étiquettes.

    Construit un index des polices disponibles au premier appel, puis
    répond aux requêtes de résolution depuis son cache.

    Args:
        substitutions: Table de substitution personnalisée. Si ``None``,
            :data:`DEFAULT_SUBSTITUTIONS` est utilisée.
    """

    def __init__(
        self,
        substitutions: dict[str, str] | None = None,
    ) -> None:
        self._substitutions = substitutions or DEFAULT_SUBSTITUTIONS
        self._font_index: dict[str, Path] | None = None
        self._cache: dict[tuple[str, bool, bool, int], ImageFont.FreeTypeFont] = {}

    def resolve(
        self,
        name: str,
        bold: bool = False,
        italic: bool = False,
        size_px: int = 12,
    ) -> ImageFont.FreeTypeFont:
        """
        Retourne un :class:`PIL.ImageFont.FreeTypeFont` pour les paramètres
        donnés.

        La résolution est mise en cache - appels répétés avec les mêmes
        paramètres ne déclenchent pas de lecture disque supplémentaire.

        Args:
            name:    Nom de la police (ex. ``"Atlanta"``).
            bold:    Gras.
            italic:  Italique.
            size_px: Taille en pixels (déjà convertie depuis les points).

        Returns:
            Police PIL prête à l'emploi.
        """
        key = (name.lower(), bold, italic, size_px)

        font = self._cache.get(key)
        if font is not None:
            return font

        font = self._load_font(name, bold, italic, size_px)
        self._cache[key] = font
        return font

    def _load_font(
        self,
        name: str,
        bold: bool,
        italic: bool,
        size_px: int,
    ) -> ImageFont.FreeTypeFont:
        """
        Charge et met en cache la police résolue.

        Ordre de résolution :
        1. Correspondance exacte (insensible à la casse) dans l'index.
        2. Substitution via la table de substitution + correspondance.
        3. Correspondance partielle sur le nom de fichier.
        4. Fallback embarqué dans ``resources/fonts/``.
        """
        index = self._get_index()
        path = (
            self._find_exact(name, bold, italic, index)
            or self._find_via_substitution(name, bold, italic, index)
            or self._find_partial(name, bold, italic, index)
            or self._fallback_path()
        )

        if path is None:
            logger.error(
                "Aucune police trouvée pour %r - PIL utilisera sa police interne.",
                name,
            )
            return cast(ImageFont.FreeTypeFont, ImageFont.load_default())

        try:
            return ImageFont.truetype(str(path), size=size_px)
        except OSError as exc:
            logger.warning("Échec du chargement de la police %s : %s", path, exc)
            return cast(ImageFont.FreeTypeFont, ImageFont.load_default())

    def _get_index(self) -> dict[str, Path]:
        """Construit l'index au premier appel (lazy init)."""
        if self._font_index is None:
            self._font_index = _scan_fonts()
        return self._font_index

    def _find_exact(
        self,
        name: str,
        bold: bool,
        italic: bool,
        index: dict[str, Path],
    ) -> Path | None:
        """Recherche exacte par nom de famille, avec préférence au style."""
        key = name.lower()
        base = index.get(key)

        if base is None:
            return None

        # Essaie de trouver une variante stylistique dans le même répertoire
        styled = self._find_style_variant(base.parent, name, bold, italic)
        return styled or base

    def _find_via_substitution(
        self,
        name: str,
        bold: bool,
        italic: bool,
        index: dict[str, Path],
    ) -> Path | None:
        """Recherche via la table de substitution."""
        substitute = self._substitutions.get(name)

        if substitute is None:
            # Recherche case-insensitive
            for key, val in self._substitutions.items():
                if key.lower() == name.lower():
                    substitute = val
                    break

        if substitute is None:
            return None

        logger.debug("Substitution de police : %r -> %r", name, substitute)
        return self._find_exact(substitute, bold, italic, index)

    def _find_partial(
        self,
        name: str,
        bold: bool,
        italic: bool,
        index: dict[str, Path],
    ) -> Path | None:
        """Correspondance partielle : le nom figure dans la clé de l'index."""
        needle = name.lower()

        for key, path in index.items():
            if needle in key:
                logger.debug("Correspondance partielle pour %r : %s", name, path)
                styled = self._find_style_variant(path.parent, key, bold, italic)
                return styled or path

        return None

    def _find_style_variant(
        self,
        directory: Path,
        family: str,
        bold: bool,
        italic: bool,
    ) -> Path | None:
        """
        Cherche un fichier TTF de style correspondant dans le répertoire donné.

        Exemple : ``DejaVuSans-BoldOblique.ttf`` pour bold+italic.
        """
        suffixes: list[str] = []

        if bold and italic:
            suffixes += ["BoldItalic", "BoldOblique", "Bold-Italic"]
        elif bold:
            suffixes += ["Bold"]
        elif italic:
            suffixes += ["Italic", "Oblique"]

        family_lower = family.lower().replace(" ", "")

        for suffix in suffixes:
            for path in directory.glob("*.ttf"):
                stem_lower = path.stem.lower().replace(" ", "").replace("-", "")
                if family_lower in stem_lower and suffix.lower() in stem_lower:
                    return path

        return None

    def _fallback_path(self) -> Path | None:
        """Retourne le chemin du fallback embarqué si disponible."""
        path = _RESOURCES_FONTS_DIR / _FALLBACK_FONT_NAME

        if path.exists():
            return path

        logger.warning(
            "Police de repli introuvable : %s. "
            "Placez DejaVuSans.ttf dans resources/fonts/.",
            path,
        )
        return None
