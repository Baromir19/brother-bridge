"""
Résolveur de noms de bande brother_ql à partir de la géométrie du papier.

Principe
--------
1. Le parser .lbx extrait ``width_pt``, ``height_pt`` et ``autoLength``
   du XML.
2. Le résolveur convertit les points PostScript en millimètres.
3. Il cherche la bande brother_ql la plus proche par distance euclidienne
   (ou distance absolue pour les bandes continues).
4. Si la distance dépasse ``MAX_DISTANCE_MM``, une exception est levée.

Aucune table de correspondance hardcodée (format 259 -> "62") n'est
nécessaire. La résolution par *nearest neighbour* avec seuil tolère
les petites erreurs d'arrondi et les variations inter-versions de
P-touch Editor.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from brother_ql.labels import ALL_LABELS, FormFactor

from ..lbx.model import PaperSpec

logger = logging.getLogger(__name__)

MAX_DISTANCE_MM: float = 2.0
"""
Seuil de distance maximale pour considérer une bande comme compatible.

- Bandes continues : distance = ``abs(width₁ - width₂)``
- Bandes die-cut :  distance = ``hypot(width₁ - width₂, height₁ - height₂)``

Une valeur de 2 mm permet d'absorber les erreurs de conversion
pt -> mm (ex. 175.7 pt -> 61.98 mm sera associé à la bande 62 mm
et non rejeté).
"""


class UnsupportedLabelError(ValueError):
    """
    Levé lorsqu'aucune bande brother_ql ne correspond aux dimensions
    déclarées dans le fichier .lbx (distance > ``MAX_DISTANCE_MM``).
    """


@dataclass(frozen=True)
class LabelGeometry:
    """
    Géométrie d'une bande brother_ql, extraite de ``ALL_LABELS``.

    Stocke les dimensions en millimètres (en flottant, sans arrondi)
    pour un calcul de distance précis.
    """

    name: str
    """Identifiant brother_ql de la bande (ex. ``"62"``, ``"103x164"``)."""

    width_mm: float
    """Largeur en millimètres."""

    height_mm: float | None
    """
    Hauteur en millimètres, ou ``None`` pour les bandes continues
    (``kind == 'continuous'``).
    """

    continuous: bool
    """``True`` si la bande est continue (pas de hauteur fixe)."""


class BrotherQlLabelResolver:
    """
    Résout un :class:`~lbx.model.PaperSpec` en nom de bande brother_ql
    par recherche du plus proche voisin avec seuil.

    L'index est construit à l'instanciation à partir de
    ``brother_ql.labels.ALL_LABELS``.

    Thread-safe : la liste des géométries est immuable après construction.
    """

    def __init__(self) -> None:
        self._labels: list[LabelGeometry] = self._build_labels()

    @staticmethod
    def _build_labels() -> list[LabelGeometry]:
        """
        Construit la liste des :class:`LabelGeometry` depuis ALL_LABELS.

        Retourne une liste (pas un dict) car la résolution est un balayage
        linéaire sur un jeu de données très petit (quelques dizaines
        d'entrées). Pas besoin d'optimisation.
        """
        geometries: list[LabelGeometry] = []

        for label in ALL_LABELS:
            geometries.append(
                LabelGeometry(
                    name=label.identifier,
                    width_mm=label.tape_size[0],
                    height_mm=label.tape_size[1]
                    if (
                        label.form_factor != FormFactor.ENDLESS
                        and label.form_factor != FormFactor.PTOUCH_ENDLESS
                    )
                    else None,
                    continuous=(
                        label.form_factor == FormFactor.ENDLESS
                        or label.form_factor == FormFactor.PTOUCH_ENDLESS
                    ),
                )
            )

        logger.debug(
            "Géométries brother_ql chargées : %d bande(s).",
            len(geometries),
        )
        return geometries

    def resolve(self, paper: PaperSpec) -> str:
        """
        Retourne le nom de bande brother_ql le plus proche du papier.

        La résolution se fait exclusivement par les dimensions (mm),
        jamais par ``paper.format_id``.

        Algorithme
        ----------
        1. Filtrer les bandes par type (continu ou die-cut).
        2. Calculer la distance :
           - continue  -> ``abs(width₁ - width₂)``
           - die-cut   -> ``hypot(dw, dh)``
        3. Sélectionner la bande avec la plus petite distance.
        4. Si la distance > ``MAX_DISTANCE_MM``, lever une exception.

        Args:
            paper: Spécification du papier extraite du XML .lbx.

        Returns:
            Identifiant de bande brother_ql (ex. ``"62"``, ``"103x164"``).

        Raises:
            UnsupportedLabelError: Si aucune bande n'est suffisamment
                proche (distance > ``MAX_DISTANCE_MM``).
        """
        candidates = [
            label for label in self._labels if label.continuous == paper.auto_length
        ]

        if not candidates:
            # Aucune bande du même type - cas théorique
            # (brother_ql a toujours au moins une continue et une die-cut)
            raise UnsupportedLabelError(
                f"Aucune bande {'continue' if paper.auto_length else 'die-cut'} "
                f"trouvée dans brother_ql pour "
                f"{paper.width_mm}x{paper.height_mm} mm."
            )

        def die_cut_distance(label: LabelGeometry) -> float:
            width = label.width_mm
            height = label.height_mm

            if width is None or height is None:
                return float("inf")

            return math.hypot(
                width - width,
                height - height,
            )

        if paper.auto_length:
            # Bande continue : distance = écart de largeur
            best = min(
                candidates,
                key=lambda label: abs(label.width_mm - paper.width_mm),
            )
            distance = abs(best.width_mm - paper.width_mm)

        else:
            # Bande die-cut : distance euclidienne
            best = min(
                candidates,
                key=die_cut_distance,
            )

            distance = die_cut_distance(best)

        if distance > MAX_DISTANCE_MM:
            raise UnsupportedLabelError(
                f"Aucune bande brother_ql trouvée pour "
                f"{paper.width_mm}x{paper.height_mm} mm "
                f"(continuous={paper.auto_length}). "
                f"La meilleure candidate est {best.name!r} "
                f"({best.width_mm}x{best.height_mm} mm) "
                f"à {distance:.2f} mm, ce qui dépasse le seuil "
                f"de {MAX_DISTANCE_MM} mm."
            )

        logger.debug(
            "Bande résolue : demande=%sx%s mm -> %r (%sx%s mm, distance=%.2f mm)",
            paper.width_mm,
            paper.height_mm if not paper.auto_length else "∞",
            best.name,
            best.width_mm,
            best.height_mm if not best.continuous else "∞",
            distance,
        )

        return best.name
