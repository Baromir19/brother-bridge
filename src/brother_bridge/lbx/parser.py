"""Parser for Brother ``.lbx`` label templates.

A ``.lbx`` file is a ZIP archive whose ``label.xml`` entry describes the paper,
the objects and their formatting. :class:`LbxParser` turns that XML into an
in-memory :class:`~brother_bridge.lbx.model.LabelLayout` without touching the
filesystem, so it can parse bytes, an open file or a network payload alike.

The parser is stateless and safe to share between threads.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path
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

_NAMESPACES: dict[str, str] = {
    "pt": "http://schemas.brother.info/ptouch/2007/lbx/main",
    "style": "http://schemas.brother.info/ptouch/2007/lbx/style",
    "text": "http://schemas.brother.info/ptouch/2007/lbx/text",
    "image": "http://schemas.brother.info/ptouch/2007/lbx/image",
    "barcode": "http://schemas.brother.info/ptouch/2007/lbx/barcode",
}


def _qualified(prefix: str, tag: str) -> str:
    return f"{{{_NAMESPACES[prefix]}}}{tag}"


_TAG_BODY = _qualified("pt", "body")
_TAG_OBJECTS = _qualified("pt", "objects")
_TAG_SHEET = _qualified("style", "sheet")
_TAG_PAPER = _qualified("style", "paper")
_TAG_OBJECT_STYLE = _qualified("pt", "objectStyle")
_TAG_EXPANDED = _qualified("pt", "expanded")
_TAG_DATA = _qualified("pt", "data")
_TAG_TEXT = _qualified("text", "text")
_TAG_PT_FONT_INFO = _qualified("text", "ptFontInfo")
_TAG_LOG_FONT = _qualified("text", "logFont")
_TAG_FONT_EXT = _qualified("text", "fontExt")
_TAG_TEXT_CONTROL = _qualified("text", "textControl")
_TAG_TEXT_ALIGN = _qualified("text", "textAlign")
_TAG_TEXT_STYLE = _qualified("text", "textStyle")
_TAG_STRING_ITEM = _qualified("text", "stringItem")
_TAG_IMAGE = _qualified("image", "image")
_TAG_BARCODE = _qualified("barcode", "barcode")

_XML_ENTRY = "label.xml"

HorizontalAlignment = Literal["LEFT", "CENTER", "RIGHT"]
VerticalAlignment = Literal["TOP", "CENTER", "BOTTOM"]

_H_ALIGNMENTS: frozenset[str] = frozenset({"LEFT", "CENTER", "RIGHT"})
_V_ALIGNMENTS: frozenset[str] = frozenset({"TOP", "CENTER", "BOTTOM"})


def _parse_pt(value: str) -> float:
    """Convert a template length such as ``"8.4pt"`` to a float."""
    return float(value.removesuffix("pt"))


def _parse_bool(value: str) -> bool:
    """Interpret a template boolean attribute (``"true"`` / ``"false"``)."""
    return value.strip().lower() == "true"


def _parse_font(font_info: ET.Element) -> FontSpec:
    """Build a :class:`FontSpec` from a ``<text:ptFontInfo>`` element."""
    log_font = font_info.find(_TAG_LOG_FONT)
    font_ext = font_info.find(_TAG_FONT_EXT)

    name = "Arial"
    size_pt = 10.0
    bold = False
    italic = False
    color = "#000000"

    if log_font is not None:
        name = log_font.get("name", name)
        italic = _parse_bool(log_font.get("italic", "false"))

        try:
            bold = int(log_font.get("weight", "400")) >= 700
        except ValueError:
            logger.debug(
                "Unreadable font weight %r for %r", log_font.get("weight"), name
            )

    if font_ext is not None:
        raw_size = font_ext.get("size", "")

        if raw_size:
            size_pt = _parse_pt(raw_size)

        color = font_ext.get("textColor", color)

    return FontSpec(name=name, size_pt=size_pt, bold=bold, italic=italic, color=color)


class LbxParser:
    """Convert ``.lbx`` bytes into a :class:`LabelLayout`.

    Example:
        >>> parser = LbxParser()
        >>> layout = parser.parse(Path("address.lbx").read_bytes())
        >>> sorted(layout.objects)
        ['address', 'title']
    """

    def parse(self, data: bytes | BinaryIO) -> LabelLayout:
        """Parse a ``.lbx`` document.

        Args:
            data: Archive content as bytes or as a binary file object.

        Returns:
            The parsed layout.

        Raises:
            ValueError: If the archive has no ``label.xml`` or required
                elements are missing.
            zipfile.BadZipFile: If the payload is not a ZIP archive.
        """
        raw = data if isinstance(data, bytes) else data.read()

        return self._parse_document(ET.fromstring(self._extract_xml(raw)))

    def parse_file(self, path: str | Path) -> LabelLayout:
        """Parse a ``.lbx`` file from disk."""
        return self.parse(Path(path).read_bytes())

    @staticmethod
    def _extract_xml(raw: bytes) -> bytes:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            if _XML_ENTRY not in archive.namelist():
                raise ValueError(
                    f"{_XML_ENTRY} is missing from the .lbx archive; "
                    "the file is probably corrupted."
                )

            return archive.read(_XML_ENTRY)

    def _parse_document(self, root: ET.Element) -> LabelLayout:
        body = root.find(_TAG_BODY)

        if body is None:
            raise ValueError("<pt:body> is missing from label.xml.")

        sheet = body.find(_TAG_SHEET)

        if sheet is None:
            raise ValueError("<style:sheet> is missing from label.xml.")

        return LabelLayout(
            paper=self._parse_paper(sheet),
            objects=self._parse_objects(sheet),
        )

    def _parse_paper(self, sheet: ET.Element) -> PaperSpec:
        element = sheet.find(_TAG_PAPER)

        if element is None:
            raise ValueError("<style:paper> is missing from label.xml.")

        orientation = element.get("orientation", "portrait").strip().lower()

        if orientation not in ("portrait", "landscape"):
            logger.debug(
                "Unknown orientation %r, falling back to portrait", orientation
            )
            orientation = "portrait"

        return PaperSpec(
            width_pt=_parse_pt(element.get("width", "0pt")),
            height_pt=_parse_pt(element.get("height", "0pt")),
            auto_length=_parse_bool(element.get("autoLength", "false")),
            margin_left_pt=_parse_pt(element.get("marginLeft", "0pt")),
            margin_top_pt=_parse_pt(element.get("marginTop", "0pt")),
            margin_right_pt=_parse_pt(element.get("marginRight", "0pt")),
            margin_bottom_pt=_parse_pt(element.get("marginBottom", "0pt")),
            orientation=cast(Literal["portrait", "landscape"], orientation),
            printer_name=element.get("printerName", ""),
            format_id=self._parse_format_id(element.get("format", "0")),
        )

    @staticmethod
    def _parse_format_id(raw: str) -> int:
        try:
            return int(raw)
        except ValueError:
            logger.debug("Unreadable paper format %r, using 0", raw)
            return 0

    def _parse_objects(self, sheet: ET.Element) -> dict[str, LabelObject]:
        objects_element = sheet.find(_TAG_OBJECTS)

        if objects_element is None:
            logger.warning("<pt:objects> is missing; the template has no objects.")
            return {}

        objects: dict[str, LabelObject] = {}

        for child in objects_element:
            parsed = self._parse_object(child)

            if parsed is None:
                continue

            if parsed.object_name in objects:
                logger.warning(
                    "Duplicate objectName %r; keeping the first occurrence.",
                    parsed.object_name,
                )
                continue

            objects[parsed.object_name] = parsed

        return objects

    def _parse_object(self, element: ET.Element) -> LabelObject | None:
        if element.tag == _TAG_TEXT:
            return self._parse_text_object(element)

        if element.tag == _TAG_IMAGE:
            return self._parse_image_object(element)

        if element.tag == _TAG_BARCODE:
            return self._parse_barcode_object(element)

        logger.debug("Ignoring unsupported object element %s", element.tag)
        return None

    @staticmethod
    def _object_name(element: ET.Element) -> str | None:
        object_style = element.find(_TAG_OBJECT_STYLE)

        if object_style is None:
            return None

        expanded = object_style.find(_TAG_EXPANDED)

        if expanded is None:
            return None

        name = expanded.get("objectName")

        return name or None

    @staticmethod
    def _object_geometry(element: ET.Element) -> tuple[float, float, float, float]:
        object_style = element.find(_TAG_OBJECT_STYLE)
        assert object_style is not None  # guarded by callers

        return (
            _parse_pt(object_style.get("x", "0pt")),
            _parse_pt(object_style.get("y", "0pt")),
            _parse_pt(object_style.get("width", "0pt")),
            _parse_pt(object_style.get("height", "0pt")),
        )

    def _parse_text_object(self, element: ET.Element) -> TextObject | None:
        object_name = self._object_name(element)

        if object_name is None:
            logger.debug("Ignoring text object without objectName.")
            return None

        font_info = element.find(_TAG_PT_FONT_INFO)
        default_font = (
            _parse_font(font_info)
            if font_info is not None
            else FontSpec(name="Arial", size_pt=10.0)
        )

        control = element.find(_TAG_TEXT_CONTROL)
        shrink = False
        auto_lf = True

        if control is not None:
            shrink = _parse_bool(control.get("shrink", "false"))
            auto_lf = _parse_bool(control.get("autoLF", "true"))

        text_style = element.find(_TAG_TEXT_STYLE)
        line_space = 0.0
        char_space = 0.0

        if text_style is not None:
            line_space = self._parse_number(text_style.get("lineSpace", "0"))
            char_space = self._parse_number(text_style.get("charSpace", "0"))

        text = self._text_content(element)
        h_align, v_align = self._parse_alignment(element)
        x_pt, y_pt, width_pt, height_pt = self._object_geometry(element)

        return TextObject(
            object_name=object_name,
            x_pt=x_pt,
            y_pt=y_pt,
            width_pt=width_pt,
            height_pt=height_pt,
            text=text,
            default_font=default_font,
            runs=self._parse_runs(element, text, default_font),
            h_align=h_align,
            v_align=v_align,
            shrink=shrink,
            line_space=line_space,
            char_space=char_space,
            auto_lf=auto_lf,
        )

    @staticmethod
    def _parse_number(raw: str) -> float:
        try:
            return float(raw)
        except ValueError:
            return 0.0

    @staticmethod
    def _text_content(element: ET.Element) -> str:
        data_element = element.find(_TAG_DATA)

        return (data_element.text or "") if data_element is not None else ""

    @staticmethod
    def _parse_alignment(
        element: ET.Element,
    ) -> tuple[HorizontalAlignment, VerticalAlignment]:
        align_element = element.find(_TAG_TEXT_ALIGN)

        if align_element is None:
            return "LEFT", "TOP"

        raw_h = align_element.get("horizontalAlignment", "LEFT").strip().upper()
        raw_v = align_element.get("verticalAlignment", "TOP").strip().upper()

        horizontal = cast(
            HorizontalAlignment, raw_h if raw_h in _H_ALIGNMENTS else "LEFT"
        )
        vertical = cast(VerticalAlignment, raw_v if raw_v in _V_ALIGNMENTS else "TOP")

        return horizontal, vertical

    def _parse_runs(
        self,
        text_element: ET.Element,
        text: str,
        default_font: FontSpec,
    ) -> list[Run]:
        """Rebuild the runs from ``<text:stringItem>`` elements.

        A single run covering the whole text is returned when there is no
        markup or when the declared lengths disagree with the text.
        """
        items = text_element.findall(_TAG_STRING_ITEM)

        if not items:
            return [Run(length=len(text), font=default_font)]

        runs: list[Run] = []
        total = 0

        for item in items:
            raw_length = item.get("charLen")

            if raw_length is None:
                continue

            try:
                length = int(raw_length)
            except ValueError:
                logger.debug("Ignoring stringItem with charLen=%r", raw_length)
                continue

            font_info = item.find(_TAG_PT_FONT_INFO)
            font = _parse_font(font_info) if font_info is not None else default_font

            runs.append(Run(length=length, font=font))
            total += length

        if total != len(text):
            logger.warning(
                "Run lengths do not match the text: sum(charLen)=%d, len(text)=%d; "
                "falling back to a single run.",
                total,
                len(text),
            )
            return [Run(length=len(text), font=default_font)]

        return runs

    def _parse_image_object(self, element: ET.Element) -> ImageObject | None:
        object_name = self._object_name(element)

        if object_name is None:
            return None

        x_pt, y_pt, width_pt, height_pt = self._object_geometry(element)
        logger.debug("Parsed image object (payload not extracted): %s", object_name)

        return ImageObject(
            object_name=object_name,
            x_pt=x_pt,
            y_pt=y_pt,
            width_pt=width_pt,
            height_pt=height_pt,
        )

    def _parse_barcode_object(self, element: ET.Element) -> BarcodeObject | None:
        object_name = self._object_name(element)

        if object_name is None:
            return None

        x_pt, y_pt, width_pt, height_pt = self._object_geometry(element)
        logger.debug("Parsed barcode object (not rendered): %s", object_name)

        return BarcodeObject(
            object_name=object_name,
            x_pt=x_pt,
            y_pt=y_pt,
            width_pt=width_pt,
            height_pt=height_pt,
            value=self._text_content(element),
        )


__all__ = ["LbxParser"]
