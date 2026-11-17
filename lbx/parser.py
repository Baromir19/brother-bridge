"""
Parseur de documents .lbx Brother.

Convertit les bytes d'un fichier .lbx (archive ZIP contenant ``label.xml``)
en un :class:`~lbx.model.LabelLayout` entièrement en mémoire.

Le parseur n'a aucune connaissance du système de fichiers : il accepte
``bytes`` ou tout objet fichier binaire. C'est l'appelant qui est
responsable de la lecture du fichier source.

Exemple d'utilisation ::

    from lbx.parser import LbxParser

    with open("template.lbx", "rb") as f:
        layout = LbxParser().parse(f)

    # ou directement depuis des bytes
    layout = LbxParser().parse(path.read_bytes())
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import BinaryIO, Literal, cast

from .model import (
    BarcodeObject,
    FontSpec,
    ImageObject,
    LabelLayout,
    LabelObject,
    PaperSpec,
    Run,
    TextObject,
)

logger = logging.getLogger(__name__)


_NS: dict[str, str] = {
    "pt": "http://schemas.brother.info/ptouch/2007/lbx/main",
    "style": "http://schemas.brother.info/ptouch/2007/lbx/style",
    "text": "http://schemas.brother.info/ptouch/2007/lbx/text",
    "image": "http://schemas.brother.info/ptouch/2007/lbx/image",
    "barcode": "http://schemas.brother.info/ptouch/2007/lbx/barcode",
    "draw": "http://schemas.brother.info/ptouch/2007/lbx/draw",
}

# Tag complets précalculés pour éviter la répétition de .format()
_TAG_PAPER = f"{{{_NS['style']}}}paper"
_TAG_OBJECTS = f"{{{_NS['pt']}}}objects"
_TAG_TEXT = f"{{{_NS['text']}}}text"
_TAG_OBJECT_STYLE = f"{{{_NS['pt']}}}objectStyle"
_TAG_EXPANDED = f"{{{_NS['pt']}}}expanded"
_TAG_PT_FONT_INFO = f"{{{_NS['text']}}}ptFontInfo"
_TAG_LOG_FONT = f"{{{_NS['text']}}}logFont"
_TAG_FONT_EXT = f"{{{_NS['text']}}}fontExt"
_TAG_TEXT_CONTROL = f"{{{_NS['text']}}}textControl"
_TAG_TEXT_ALIGN = f"{{{_NS['text']}}}textAlign"
_TAG_TEXT_STYLE = f"{{{_NS['text']}}}textStyle"
_TAG_PT_DATA = f"{{{_NS['pt']}}}data"
_TAG_STRING_ITEM = f"{{{_NS['text']}}}stringItem"
_TAG_IMAGE = f"{{{_NS['image']}}}image"
_TAG_BARCODE = f"{{{_NS['barcode']}}}barcode"


def _pt(value: str) -> float:
    """
    Convertit une valeur ``"XX.XXpt"`` en float.

    Args:
        value: Chaîne au format Brother (ex. ``"8.4pt"``).

    Returns:
        Valeur numérique en points PostScript.

    Raises:
        ValueError: Si la chaîne n'est pas au format attendu.
    """
    return float(value.removesuffix("pt"))


def _bool_attr(value: str) -> bool:
    return value.lower() == "true"


def _parse_font(font_info_el: ET.Element) -> FontSpec:
    """
    Extrait un :class:`FontSpec` depuis un élément ``<text:ptFontInfo>``.

    Args:
        font_info_el: Élément ``<text:ptFontInfo>`` du XML.

    Returns:
        Instance de :class:`FontSpec` peuplée.
    """
    log_font = font_info_el.find(_TAG_LOG_FONT)
    font_ext = font_info_el.find(_TAG_FONT_EXT)

    name = "Arial"
    bold = False
    italic = False
    size_pt = 10.0
    color = "#000000"

    if log_font is not None:
        name = log_font.get("name", name)
        italic = _bool_attr(log_font.get("italic", "false"))
        weight = int(log_font.get("weight", "400"))
        bold = weight >= 700

    if font_ext is not None:
        raw_size = font_ext.get("size", "")
        if raw_size:
            size_pt = _pt(raw_size)
        color = font_ext.get("textColor", color)

    return FontSpec(
        name=name,
        size_pt=size_pt,
        bold=bold,
        italic=italic,
        color=color,
    )


class LbxParser:
    """
    Parseur de documents .lbx Brother.

    Instancier une fois et réutiliser - la classe ne conserve aucun état
    entre deux appels à :meth:`parse`.
    """

    def parse(self, data: bytes | BinaryIO) -> LabelLayout:
        """
        Parse un document .lbx et retourne le layout en mémoire.

        Args:
            data: Contenu du fichier .lbx sous forme de ``bytes`` ou d'un
                  objet fichier binaire ouvert en lecture.

        Returns:
            :class:`~lbx.model.LabelLayout` prêt à l'emploi.

        Raises:
            ValueError: Si ``label.xml`` est absent de l'archive.
            zipfile.BadZipFile: Si les données ne constituent pas un ZIP valide.
        """
        raw = data if isinstance(data, bytes) else data.read()
        xml_bytes = self._extract_xml(raw)
        root = ET.fromstring(xml_bytes)
        return self._parse_document(root)

    @staticmethod
    def _extract_xml(raw: bytes) -> bytes:
        """
        Extrait ``label.xml`` depuis l'archive ZIP en mémoire.

        Args:
            raw: Contenu brut du fichier .lbx.

        Returns:
            Bytes du fichier ``label.xml``.

        Raises:
            ValueError: Si ``label.xml`` est absent.
        """
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            if "label.xml" not in zf.namelist():
                raise ValueError(
                    "Fichier label.xml absent de l'archive .lbx. "
                    "Le fichier source est peut-être corrompu."
                )
            return zf.read("label.xml")

    def _parse_document(self, root: ET.Element) -> LabelLayout:
        """Parcourt ``<pt:document>`` -> ``<pt:body>`` -> ``<style:sheet>``."""
        body = root.find(f"{{{_NS['pt']}}}body")

        if body is None:
            raise ValueError("Élément <pt:body> introuvable dans label.xml.")

        sheet = body.find(f"{{{_NS['style']}}}sheet")

        if sheet is None:
            raise ValueError("Élément <style:sheet> introuvable dans label.xml.")

        paper = self._parse_paper(sheet)
        objects = self._parse_objects(sheet)

        return LabelLayout(paper=paper, objects=objects)

    def _parse_paper(self, sheet: ET.Element) -> PaperSpec:
        """Extrait les dimensions et paramètres du support depuis ``<style:paper>``."""
        el = sheet.find(_TAG_PAPER)

        if el is None:
            raise ValueError("Élément <style:paper> introuvable dans label.xml.")

        format_id_str = el.get("format", "0")

        return PaperSpec(
            width_pt=_pt(el.get("width", "0pt")),
            height_pt=_pt(el.get("height", "0pt")),
            auto_length=_bool_attr(el.get("autoLength", "false")),
            margin_left_pt=_pt(el.get("marginLeft", "0pt")),
            margin_top_pt=_pt(el.get("marginTop", "0pt")),
            margin_right_pt=_pt(el.get("marginRight", "0pt")),
            margin_bottom_pt=_pt(el.get("marginBottom", "0pt")),
            orientation=cast(
                Literal["portrait", "landscape"],
                el.get("orientation", "portrait").lower(),
            ),
            printer_name=el.get("printerName", ""),
            format_id=int(format_id_str),
        )

    def _parse_objects(self, sheet: ET.Element) -> dict[str, LabelObject]:
        """
        Parcourt ``<pt:objects>`` et construit le dictionnaire d'objets.

        Les objets sans ``objectName`` sont ignorés avec un avertissement.
        """
        objects_el = sheet.find(_TAG_OBJECTS)

        if objects_el is None:
            logger.warning("<pt:objects> introuvable - étiquette sans objets.")
            return {}

        result: dict[str, LabelObject] = {}

        for child in objects_el:
            tag = child.tag
            obj: LabelObject | None = None

            if tag == _TAG_TEXT:
                obj = self._parse_text_object(child)
            elif tag == _TAG_IMAGE:
                obj = self._parse_image_object(child)
            elif tag == _TAG_BARCODE:
                obj = self._parse_barcode_object(child)
            else:
                logger.debug("Objet de type inconnu ignoré : %s", tag)
                continue

            if obj is not None:
                if obj.object_name in result:
                    logger.warning(
                        "Doublon d'objectName %r - le premier est conservé.",
                        obj.object_name,
                    )
                else:
                    result[obj.object_name] = obj

        return result

    def _parse_text_object(self, el: ET.Element) -> TextObject | None:
        """
        Parse un élément ``<text:text>`` en :class:`TextObject`.

        Returns:
            Instance de :class:`TextObject`, ou ``None`` si l'objet ne
            possède pas de ``objectName`` (objet non adressable).
        """
        object_style = el.find(_TAG_OBJECT_STYLE)

        if object_style is None:
            logger.debug("<pt:objectStyle> absent dans <text:text> - ignoré.")
            return None

        # Nom de l'objet
        expanded = object_style.find(_TAG_EXPANDED)
        object_name = expanded.get("objectName") if expanded is not None else None

        if not object_name:
            logger.debug("Objet texte sans objectName - ignoré.")
            return None

        # Bounding box
        x_pt = _pt(object_style.get("x", "0pt"))
        y_pt = _pt(object_style.get("y", "0pt"))
        width_pt = _pt(object_style.get("width", "0pt"))
        height_pt = _pt(object_style.get("height", "0pt"))

        # Police par défaut de l'objet
        font_info = el.find(_TAG_PT_FONT_INFO)
        default_font = (
            _parse_font(font_info)
            if font_info is not None
            else FontSpec(name="Arial", size_pt=10.0)
        )

        # Alignement
        align_el = el.find(_TAG_TEXT_ALIGN)

        # Contrôle (shrink)
        control_el = el.find(_TAG_TEXT_CONTROL)
        shrink = False
        auto_lf = True

        if control_el is not None:
            shrink = _bool_attr(control_el.get("shrink", "false"))

            auto_lf = _bool_attr(control_el.get("autoLF", "true"))

        # Espacement
        style_el = el.find(_TAG_TEXT_STYLE)
        line_space = 0.0
        char_space = 0.0
        if style_el is not None:
            line_space = float(style_el.get("lineSpace", "0"))
            char_space = float(style_el.get("charSpace", "0"))

        # Texte canonique
        data_el = el.find(_TAG_PT_DATA)
        text = (data_el.text or "") if data_el is not None else ""

        # Runs (stringItem)
        runs = self._parse_runs(el, text, default_font)

        align_el = el.find(_TAG_TEXT_ALIGN)

        h_align_value: Literal["LEFT", "CENTER", "RIGHT"] = "LEFT"
        v_align_value: Literal["TOP", "CENTER", "BOTTOM"] = "TOP"

        if align_el is not None:
            raw_h_align = align_el.get("horizontalAlignment", "LEFT").upper()
            raw_v_align = align_el.get("verticalAlignment", "TOP").upper()

            h_align_value = cast(
                Literal["LEFT", "CENTER", "RIGHT"],
                raw_h_align,
            )

            v_align_value = cast(
                Literal["TOP", "CENTER", "BOTTOM"],
                raw_v_align,
            )

        return TextObject(
            object_name=object_name,
            x_pt=x_pt,
            y_pt=y_pt,
            width_pt=width_pt,
            height_pt=height_pt,
            text=text,
            default_font=default_font,
            runs=runs,
            h_align=h_align_value,
            v_align=v_align_value,
            shrink=shrink,
            line_space=line_space,
            char_space=char_space,
            auto_lf=auto_lf,
        )

    def _parse_runs(
        self,
        text_el: ET.Element,
        text: str,
        default_font: FontSpec,
    ) -> list[Run]:
        """
        Reconstruit les runs depuis les éléments ``<text:stringItem>``.

        Si aucun ``stringItem`` n'est présent, ou si la somme des longueurs
        ne correspond pas à ``len(text)``, un unique run couvrant tout le
        texte est retourné.

        Args:
            text_el:      Élément ``<text:text>`` parent.
            text:         Texte canonique (``<pt:data>``).
            default_font: Police de l'objet, utilisée si un stringItem
                          ne possède pas son propre ``<text:ptFontInfo>``.

        Returns:
            Liste de :class:`Run` cohérente avec ``text``.
        """
        items = text_el.findall(_TAG_STRING_ITEM)

        if not items:
            return [Run(length=len(text), font=default_font)]

        runs: list[Run] = []
        total = 0

        for item in items:
            char_len_str = item.get("charLen")

            if char_len_str is None:
                continue

            char_len = int(char_len_str)
            font_info = item.find(_TAG_PT_FONT_INFO)
            font = _parse_font(font_info) if font_info is not None else default_font

            runs.append(Run(length=char_len, font=font))
            total += char_len

        # Validation de cohérence
        if total != len(text):
            logger.warning(
                "Incohérence des runs pour l'objet : somme charLen=%d "
                "≠ len(text)=%d. Réinitialisation à un run unique.",
                total,
                len(text),
            )
            return [Run(length=len(text), font=default_font)]

        return runs

    def _parse_image_object(self, el: ET.Element) -> ImageObject | None:
        """
        Parse un élément ``<image:image>``.

        La récupération des données image embarquées n'est pas encore
        implémentée - retourne un objet vide positionné correctement.
        """
        object_style = el.find(_TAG_OBJECT_STYLE)

        if object_style is None:
            return None

        expanded = object_style.find(_TAG_EXPANDED)
        object_name = expanded.get("objectName") if expanded is not None else None

        if not object_name:
            return None

        logger.debug("Objet image parsé (données non extraites) : %s", object_name)

        return ImageObject(
            object_name=object_name,
            x_pt=_pt(object_style.get("x", "0pt")),
            y_pt=_pt(object_style.get("y", "0pt")),
            width_pt=_pt(object_style.get("width", "0pt")),
            height_pt=_pt(object_style.get("height", "0pt")),
        )

    def _parse_barcode_object(self, el: ET.Element) -> BarcodeObject | None:
        """
        Parse un élément ``<barcode:barcode>``.

        Le rendu des codes-barres n'est pas encore implémenté - retourne
        un objet positionné avec la valeur textuelle si disponible.
        """
        object_style = el.find(_TAG_OBJECT_STYLE)

        if object_style is None:
            return None

        expanded = object_style.find(_TAG_EXPANDED)
        object_name = expanded.get("objectName") if expanded is not None else None

        if not object_name:
            return None

        data_el = el.find(_TAG_PT_DATA)
        value = (data_el.text or "") if data_el is not None else ""

        logger.debug(
            "Objet code-barres parsé (non rendu) : %s = %r", object_name, value
        )

        return BarcodeObject(
            object_name=object_name,
            x_pt=_pt(object_style.get("x", "0pt")),
            y_pt=_pt(object_style.get("y", "0pt")),
            width_pt=_pt(object_style.get("width", "0pt")),
            height_pt=_pt(object_style.get("height", "0pt")),
            value=value,
        )
