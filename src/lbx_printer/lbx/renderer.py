"""Render a parsed label into a monochrome Pillow image.

The renderer is the only component that knows about typography. It works
entirely in memory and returns an image whose width matches the tape width in
dots at the configured resolution, which is what every print backend expects.

Layout rules implemented here:

* Canvas resolution is 300 DPI by default, the native resolution of Brother QL
  printers.
* Continuous tape (``auto_length``) derives its length from the object
  bounding boxes plus the paper margins.
* ``shrink`` objects are measured with real word wrapping and the font size is
  reduced in steps until the text fits, with a lower bound of 4 pt.
* Horizontal and vertical alignment follow the template attributes.
* Landscape designs are rendered with swapped axes and rotated by 270 degrees,
  which produces the orientation the printer expects.
"""

from __future__ import annotations

import logging

from PIL import Image, ImageDraw, ImageFont

from .fonts import FontResolver
from .model import FontSpec, LabelLayout, TextObject

logger = logging.getLogger(__name__)

DEFAULT_DPI = 300
_PT_PER_INCH = 72.0
_MIN_FONT_SIZE_PT = 4.0
_SHRINK_STEP_PT = 0.5
_BG_COLOR = 255
_FG_COLOR = 0


def _pt_to_px(pt: float, dpi: int) -> int:
    """Convert a length from points to whole pixels (at least one)."""
    return max(1, round(pt * dpi / _PT_PER_INCH))


def _font_size_px(size_pt: float, dpi: int) -> int:
    """Convert a font size from points to whole pixels (at least one)."""
    return max(1, round(size_pt * dpi / _PT_PER_INCH))


class LbxRenderer:
    """Turn a :class:`LabelLayout` into a one-bit image.

    Args:
        font_resolver: Font resolver to use. A default instance is created when
            omitted.
        dpi: Rendering resolution in dots per inch.

    The renderer keeps no state between calls, so one instance can be reused
    for concurrent renders as long as the injected resolver is thread-safe
    (the default one is).
    """

    def __init__(
        self,
        font_resolver: FontResolver | None = None,
        dpi: int = DEFAULT_DPI,
    ) -> None:
        self._fonts = font_resolver or FontResolver()
        self.dpi = dpi

    def render(self, layout: LabelLayout) -> Image.Image:
        """Render ``layout`` and return a mode ``"1"`` image.

        Args:
            layout: Parsed layout, optionally modified through ``set_field``.

        Returns:
            Monochrome image sized for direct transmission to a printer.
        """
        width_px, height_px = self._canvas_size(layout)

        image = Image.new("L", (width_px, height_px), color=_BG_COLOR)
        draw = ImageDraw.Draw(image)

        for obj in layout.objects.values():
            if not isinstance(obj, TextObject):
                logger.debug(
                    "Object %r of type %r is parsed but not rendered.",
                    obj.object_name,
                    obj.object_type,
                )
                continue

            self._render_text(
                draw,
                obj,
                layout.paper.margin_left_pt,
                layout.paper.margin_top_pt,
            )

        if layout.paper.orientation == "landscape":
            image = image.rotate(270, expand=True)

        return image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    def _canvas_size(self, layout: LabelLayout) -> tuple[int, int]:
        paper = layout.paper

        if paper.orientation == "landscape":
            width_pt = paper.height_pt
            height_pt = paper.width_pt

            if paper.auto_length and layout.objects:
                content_right_pt = max(
                    obj.x_pt + obj.width_pt for obj in layout.objects.values()
                )
                width_pt = (
                    paper.margin_left_pt + content_right_pt + paper.margin_right_pt
                )
        else:
            width_pt = paper.width_pt
            height_pt = paper.height_pt

            if paper.auto_length and layout.objects:
                content_bottom_pt = max(
                    obj.y_pt + obj.height_pt for obj in layout.objects.values()
                )
                height_pt = (
                    paper.margin_top_pt + content_bottom_pt + paper.margin_bottom_pt
                )

        width_px = _pt_to_px(width_pt, self.dpi)
        height_px = _pt_to_px(height_pt, self.dpi)

        logger.debug(
            "Canvas (%s): %d x %d px at %d DPI",
            paper.orientation,
            width_px,
            height_px,
            self.dpi,
        )

        return width_px, height_px

    def _render_text(
        self,
        draw: ImageDraw.ImageDraw,
        obj: TextObject,
        margin_left_pt: float,
        margin_top_pt: float,
    ) -> None:
        if not obj.text:
            return

        bbox_x = _pt_to_px(margin_left_pt + obj.x_pt, self.dpi)
        bbox_y = _pt_to_px(margin_top_pt + obj.y_pt, self.dpi)
        bbox_w = _pt_to_px(obj.width_pt, self.dpi)
        bbox_h = _pt_to_px(obj.height_pt, self.dpi)

        runs = obj.iter_runs()
        font_size_pt = self._resolve_font_size(draw, runs, obj, bbox_w, bbox_h)

        self._draw_runs(
            draw,
            runs,
            font_size_pt,
            obj,
            bbox_x,
            bbox_y,
            bbox_w,
            bbox_h,
        )

    def _resolve_font_size(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, FontSpec]],
        obj: TextObject,
        bbox_w: int,
        bbox_h: int,
    ) -> float:
        """Return the effective font size in points.

        Non-shrinking objects keep their declared size. Shrinking objects start
        from the smallest run size (Brother stores the result of its own shrink
        pass there) and step down until the wrapped text fits the bounding box.
        """
        if not obj.shrink:
            return obj.default_font.size_pt

        size_pt = min(font.size_pt for _, font in runs)

        while size_pt >= _MIN_FONT_SIZE_PT:
            total_w, total_h = self._measure_runs(draw, runs, size_pt, bbox_w, obj)

            if total_w <= bbox_w and total_h <= bbox_h:
                break

            size_pt -= _SHRINK_STEP_PT

        return max(size_pt, _MIN_FONT_SIZE_PT)

    def _wrap_lines(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, FontSpec]],
        size_pt: float,
        bbox_w: int,
        obj: TextObject | None = None,
    ) -> list[tuple[str, int, int]]:
        """Split the text into visual lines that fit ``bbox_w``.

        Explicit newlines always break a line. Inside a paragraph, words are
        added until the next one would overflow; a single word wider than the
        box is kept intact and allowed to overflow instead of being truncated.

        Returns:
            Tuples ``(line_text, start_offset, end_offset)`` where the offsets
            address the concatenated text of all runs.
        """
        full_text = "".join(text for text, _ in runs)

        if obj is not None and not obj.auto_lf:
            return self._wrap_explicit_lines(full_text)

        shrink = obj.shrink if obj is not None else False
        reference_font = runs[0][1] if runs else FontSpec("Arial", size_pt)
        pil_font = self._get_pil_font(reference_font, size_pt if shrink else None)

        result: list[tuple[str, int, int]] = []
        paragraph_start = 0

        for paragraph in full_text.split("\n"):
            words: list[tuple[str, int, int]] = []
            cursor = paragraph_start

            for word in paragraph.split(" "):
                words.append((word, cursor, cursor + len(word)))
                cursor += len(word) + 1

            line_words: list[tuple[str, int, int]] = []

            def flush_line(words_in_line: list[tuple[str, int, int]]) -> None:
                if not words_in_line:
                    return

                line_text = " ".join(word for word, _, _ in words_in_line)
                end = words_in_line[-1][2]

                if end < len(full_text) and full_text[end] == " ":
                    end += 1

                result.append((line_text, words_in_line[0][1], end))

            for word, word_start, word_end in words:
                candidate = [*line_words, (word, word_start, word_end)]
                candidate_text = " ".join(item[0] for item in candidate)
                bbox = draw.textbbox((0, 0), candidate_text, font=pil_font)
                width = bbox[2] - bbox[0]

                if width <= bbox_w or not line_words:
                    line_words = candidate
                else:
                    flush_line(line_words)
                    line_words = [(word, word_start, word_end)]

            flush_line(line_words)
            paragraph_start = cursor

        return result

    @staticmethod
    def _wrap_explicit_lines(full_text: str) -> list[tuple[str, int, int]]:
        """Split on explicit newlines only (``autoLF = false``)."""
        result: list[tuple[str, int, int]] = []
        start = 0

        for line in full_text.split("\n"):
            end = start + len(line)
            result.append((line, start, end))
            start = end + 1

        return result

    def _line_spacing_px(self, obj: TextObject | None, font_size_pt: float) -> int:
        """Return the vertical gap between two lines, in pixels.

        Pillow adds no leading, so a base gap of roughly 25 % of the font
        height is applied on top of the ``lineSpace`` value of the template.
        """
        extra = 0

        if obj is not None and obj.line_space:
            extra = _pt_to_px(obj.line_space, self.dpi)

        font_px = _font_size_px(font_size_pt, self.dpi)

        return round(font_px * 0.25) + extra

    def _char_spacing_px(self, obj: TextObject | None) -> int:
        """Return the character spacing of ``obj`` in pixels."""
        if obj is None or not obj.char_space:
            return 0

        return _pt_to_px(obj.char_space, self.dpi)

    def _measure_runs(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, FontSpec]],
        size_pt: float,
        bbox_w: int,
        obj: TextObject | None = None,
    ) -> tuple[int, int]:
        """Measure the wrapped text; returns ``(max line width, total height)``."""
        lines = self._wrap_lines(draw, runs, size_pt, bbox_w, obj)

        max_w = 0
        total_h = 0
        line_spacing = self._line_spacing_px(obj, size_pt)

        for _, line_start, line_end in lines:
            line_runs = self._slice_runs_for_line(
                runs, line_start, line_end - line_start
            )
            line_w = self._measure_line_width(draw, line_runs, size_pt, obj)
            line_h = self._measure_line_height(draw, line_runs, size_pt)

            max_w = max(max_w, line_w)
            total_h += line_h + line_spacing

        return max_w, total_h

    def _draw_runs(
        self,
        draw: ImageDraw.ImageDraw,
        runs: list[tuple[str, FontSpec]],
        size_pt: float,
        obj: TextObject,
        bbox_x: int,
        bbox_y: int,
        bbox_w: int,
        bbox_h: int,
    ) -> None:
        """Draw every wrapped line with horizontal and vertical alignment."""
        lines = self._wrap_lines(draw, runs, size_pt, bbox_w, obj)
        _, total_h = self._measure_runs(draw, runs, size_pt, bbox_w, obj)

        if obj.v_align == "CENTER":
            start_y = bbox_y + (bbox_h - total_h) // 2
        elif obj.v_align == "BOTTOM":
            start_y = bbox_y + bbox_h - total_h
        else:
            start_y = bbox_y

        current_y = start_y
        line_spacing = self._line_spacing_px(obj, size_pt)
        char_spacing = self._char_spacing_px(obj)

        for _, line_start, line_end in lines:
            line_runs = self._slice_runs_for_line(
                runs, line_start, line_end - line_start
            )

            line_w = self._measure_line_width(draw, line_runs, size_pt, obj)
            line_h = self._measure_line_height(draw, line_runs, size_pt)

            if obj.h_align == "CENTER":
                start_x = bbox_x + (bbox_w - line_w) // 2
            elif obj.h_align == "RIGHT":
                start_x = bbox_x + bbox_w - line_w
            else:
                start_x = bbox_x

            current_x = start_x

            for run_text, font_spec in line_runs:
                if not run_text:
                    continue

                pil_font = self._get_pil_font(font_spec, size_pt)
                bbox = draw.textbbox((0, 0), run_text, font=pil_font)

                draw.text(
                    (current_x, current_y - bbox[1]),
                    run_text,
                    font=pil_font,
                    fill=_FG_COLOR,
                )

                current_x += int(bbox[2] - bbox[0]) + char_spacing

            current_y += line_h + line_spacing

    @staticmethod
    def _slice_runs_for_line(
        runs: list[tuple[str, FontSpec]],
        line_start: int,
        line_len: int,
    ) -> list[tuple[str, FontSpec]]:
        """Return the ``(segment, font)`` pairs that cover one line."""
        result: list[tuple[str, FontSpec]] = []
        full_text = "".join(text for text, _ in runs)
        line_text = full_text[line_start : line_start + line_len]
        offset = 0

        for run_text, font in runs:
            run_start = offset
            run_end = run_start + len(run_text)
            segment_start = max(run_start, line_start)
            segment_end = min(run_end, line_start + line_len)

            if segment_start < segment_end:
                result.append((full_text[segment_start:segment_end], font))

            offset = run_end

        if result:
            return result

        return [(line_text, runs[0][1] if runs else FontSpec("Arial", 10.0))]

    def _measure_line_width(
        self,
        draw: ImageDraw.ImageDraw,
        line_runs: list[tuple[str, FontSpec]],
        size_pt: float | None = None,
        obj: TextObject | None = None,
    ) -> int:
        total = 0
        char_spacing = self._char_spacing_px(obj)

        for text, font_spec in line_runs:
            if not text:
                continue

            pil_font = self._get_pil_font(font_spec, size_pt)
            bbox = draw.textbbox((0, 0), text, font=pil_font)
            total += int(bbox[2] - bbox[0]) + char_spacing * len(text)

        return total

    def _measure_line_height(
        self,
        draw: ImageDraw.ImageDraw,
        line_runs: list[tuple[str, FontSpec]],
        size_pt: float,
    ) -> int:
        """Return the line height from font metrics.

        ``getmetrics`` is used instead of ``textbbox`` because the latter only
        reports the visible glyph box, which underestimates the line height of
        fonts whose capitals are shorter than the em box.
        """
        max_h = 0

        for text, font_spec in line_runs:
            if not text:
                continue

            pil_font = self._get_pil_font(font_spec, size_pt)
            ascent, descent = pil_font.getmetrics()
            max_h = max(max_h, ascent + descent)

        return max_h or _font_size_px(size_pt, self.dpi)

    def _get_pil_font(
        self,
        font_spec: FontSpec,
        override_size_pt: float | None = None,
    ) -> ImageFont.FreeTypeFont:
        size_pt = (
            override_size_pt if override_size_pt is not None else font_spec.size_pt
        )

        return self._fonts.resolve(
            name=font_spec.name,
            bold=font_spec.bold,
            italic=font_spec.italic,
            size_px=_font_size_px(size_pt, self.dpi),
        )


__all__ = ["DEFAULT_DPI", "LbxRenderer"]
