"""
Modèle de données interne pour les documents d'étiquettes .lbx.

Ces dataclasses représentent la structure d'une étiquette Brother après
parsing du XML. Elles sont indépendantes du format .lbx, de PIL et de
CUPS - ce sont de pures structures de données.

Hiérarchie :

    LabelLayout
      ├── PaperSpec
      └── dict[str, LabelObject]
            ├── TextObject(LabelObject)
            │     ├── FontSpec
            │     └── list[Run]
            ├── BarcodeObject(LabelObject)   [extensibilité future]
            └── ImageObject(LabelObject)     [extensibilité future]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from ..exceptions import LabelFieldNotFoundError

PT_TO_MM: float = 25.4 / 72.0
"""
Facteur de conversion des points PostScript en millimètres.

Utilisé pour dériver automatiquement le nom de bande brother_ql
à partir des dimensions en points déclarées dans le XML .lbx,
sans passer par les IDs de format hardcodés.
"""


@dataclass(frozen=True)
class FontSpec:
    """
    Spécification de police extraite du XML Brother.

    Les instances sont immuables pour permettre le partage sans risque de
    mutation accidentelle (notamment lors de la copie des runs par défaut).
    """

    name: str
    """Nom de la police tel qu'indiqué dans le XML (ex. ``"Atlanta"``)."""

    size_pt: float
    """Taille en points PostScript (1 pt = 1/72 pouce)."""

    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    """Couleur hexadécimale au format ``"#RRGGBB"``."""


@dataclass
class Run:
    """
    Portion de texte partageant un même style de police.

    Correspond à un ``<text:stringItem>`` dans le XML .lbx.
    Le texte réel est obtenu en tranchant :attr:`TextObject.text`
    avec les offsets calculés à partir des longueurs cumulées.

    Invariant : la somme de ``length`` de tous les runs d'un ``TextObject``
    doit être égale à ``len(TextObject.text)``.
    """

    length: int
    """Nombre de caractères couverts (= ``charLen`` dans le XML)."""

    font: FontSpec
    """Police appliquée à ce run."""


class LabelObject(ABC):
    """
    Classe de base abstraite pour tous les objets d'une étiquette.

    Chaque objet possède un nom (clé pour :meth:`LabelLayout.get_object`),
    une position et des dimensions en points PostScript.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    @property
    @abstractmethod
    def object_type(self) -> Literal["text", "barcode", "image"]:
        """Type de l'objet, utilisé par le renderer pour le dispatch."""


@dataclass
class TextObject(LabelObject):
    """
    Objet texte d'une étiquette.

    ``text`` est la source canonique du contenu textuel.
    ``runs`` décrit le formatage par portions ; il est toujours cohérent
    avec ``text`` (somme des longueurs = ``len(text)``).

    Lors d'un appel à :meth:`set_text`, ``runs`` est réinitialisé à un
    unique run couvrant tout le nouveau texte avec ``default_font``.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    text: str
    """Source canonique du texte (correspond à ``<pt:data>`` dans le XML)."""

    default_font: FontSpec
    """Police de référence de l'objet (``<text:ptFontInfo>`` principal)."""

    runs: list[Run]
    """Segments de formatage. Doit rester cohérent avec ``text``."""

    h_align: Literal["LEFT", "CENTER", "RIGHT"] = "LEFT"
    v_align: Literal["TOP", "CENTER", "BOTTOM"] = "TOP"
    shrink: bool = False
    line_space: float = 0.0
    char_space: float = 0.0

    auto_lf: bool = True

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "text"

    def set_text(self, value: str) -> None:
        """
        Remplace le texte et réinitialise les runs.

        Le formatage per-run de l'original est abandonné au profit d'un
        unique run avec ``default_font``. Ce comportement est intentionnel :
        les données injectées via ``set_field`` remplacent le contenu du
        template, pas son style de base.

        Args:
            value: Nouveau contenu textuel.
        """
        self.text = value
        self.runs = [Run(length=len(value), font=self.default_font)]

    def iter_runs(self) -> list[tuple[str, FontSpec]]:
        """
        Retourne la liste des segments ``(texte, police)``.

        Reconstruit les tranches de ``text`` à partir des longueurs des runs.
        Utilisé par le renderer pour dessiner le texte run par run.

        Returns:
            Liste de tuples ``(sous-texte, FontSpec)`` dans l'ordre du texte.
        """
        result: list[tuple[str, FontSpec]] = []
        offset = 0

        for run in self.runs:
            end = offset + run.length
            result.append((self.text[offset:end], run.font))
            offset = end

        return result


@dataclass
class BarcodeObject(LabelObject):
    """
    Objet code-barres d'une étiquette.

    Non rendu dans cette version - réservé pour les extensions futures.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    value: str = ""
    barcode_type: str = "CODE128"

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "barcode"


@dataclass
class ImageObject(LabelObject):
    """
    Objet image embarquée dans une étiquette.

    Non rendu dans cette version - réservé pour les extensions futures.
    """

    object_name: str
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float

    data: bytes = field(default_factory=bytes)
    """Données brutes de l'image (PNG, BMP…) extraites de l'archive .lbx."""

    @property
    def object_type(self) -> Literal["text", "barcode", "image"]:
        return "image"


@dataclass
class PaperSpec:
    """
    Spécification du support d'impression extraite de ``<style:paper>``.
    """

    width_pt: float
    height_pt: float
    auto_length: bool
    """Si ``True``, la hauteur est calculée dynamiquement selon le contenu."""

    margin_left_pt: float = 0.0
    margin_top_pt: float = 0.0
    margin_right_pt: float = 0.0
    margin_bottom_pt: float = 0.0

    orientation: Literal["portrait", "landscape"] = "portrait"
    """Orientation du design dans P-touch Editor. ``"landscape"`` signifie
    que l'axe X du canvas de design correspond à la longueur de la bande
    (``height_pt`` dans le XML) et l'axe Y à la largeur physique
    (``width_pt`` dans le XML)."""

    printer_name: str = ""
    """
    Nom d'imprimante extrait du XML (ex. ``"Brother QL-1110NWB"``).
    Utilisé comme imprimante par défaut si aucune n'est spécifiée à
    l'impression.
    """

    format_id: int = 0
    """
    Identifiant numérique ``format`` extrait de ``<style:paper>``
    (ex. ``259``, ``385``). Conservé pour logs et diagnostic ;
    jamais utilisé pour la résolution du nom de bande brother_ql.
    """

    @property
    def width_mm(self) -> int:
        """Largeur en millimètres, arrondie à l'entier."""
        return round(self.width_pt * PT_TO_MM)

    @property
    def height_mm(self) -> int | None:
        """
        Hauteur en millimètres, arrondie à l'entier.
        Retourne ``None`` pour les bandes continues (``auto_length=True``).
        """
        if self.auto_length:
            return None
        return round(self.height_pt * PT_TO_MM)


@dataclass
class LabelLayout:
    """
    Représentation complète d'une étiquette prête à être rendue.

    ``objects`` est indexé par ``object_name`` pour un accès O(1) dans
    :meth:`get_object` - appelé à chaque ``set_field``.
    """

    paper: PaperSpec
    objects: dict[str, LabelObject]
    """Objets de l'étiquette indexés par leur nom (``objectName`` XML)."""

    def get_object(self, name: str) -> LabelObject:
        """
        Retourne l'objet identifié par ``name``.

        Args:
            name: Valeur de ``objectName`` dans le XML.

        Raises:
            LabelFieldNotFoundError: Si aucun objet ne correspond à ce nom.
        """
        try:
            return self.objects[name]
        except KeyError:
            raise LabelFieldNotFoundError(
                f"Objet introuvable dans le modèle d'étiquette : {name!r}"
            ) from None
