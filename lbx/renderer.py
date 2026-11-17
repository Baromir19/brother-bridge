"""
Renderer d'étiquettes Brother .lbx vers PIL.Image.

Convertit un :class:`~lbx.model.LabelLayout` en image monochrome
``PIL.Image`` prête à être envoyée à l'imprimante (CUPS ou Brother QL
direct). Aucune écriture disque n'est effectuée - tout se passe en mémoire.

Résolution cible
----------------
300 DPI est la résolution native des imprimantes Brother QL.
La constante peut être surchargée via :attr:`LbxRenderer.dpi`.

AutoLength
----------
Si ``paper.auto_length`` est ``True``, la hauteur du canvas est calculée
dynamiquement à partir de la bounding-box des objets, en y ajoutant les
marges du papier. La hauteur déclarée dans le XML est ignorée.

Shrink avec word-wrap
---------------------
Pour les objets avec ``shrink=True``, la taille de police est réduite
par pas de 0.5 pt jusqu'à ce que le texte tienne dans la bounding-box,
avec un plancher à 4 pt.

Contrairement à l'ancienne version qui mesurait chaque ligne entière sans
retour à la ligne (``full_text.split("\\n")``), la version actuelle applique
un vrai *word-wrap* : le texte est découpé mot par mot selon la largeur
disponible ``bbox_w``. Ceci corrige le bug où des objets avec un long texte
(comme l'adresse ~140 caractères sans ``\\n``) forçaient toujours la police
à 4.0 pt, leur taille minimale.

Alignement
----------
L'alignement horizontal (LEFT / CENTER / RIGHT) et vertical (TOP / CENTER /
BOTTOM) est appliqué à chaque objet selon les attributs du XML.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from PIL import Image, ImageDraw, ImageFont

from .fonts import FontResolver
from .model import FontSpec, LabelLayout, TextObject

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_DEFAULT_DPI = 300
_PT_PER_INCH = 72.0
_MIN_FONT_SIZE_PT = 4.0
_SHRINK_STEP_PT = 0.5
_BG_COLOR = 255  # blanc en niveaux de gris
_FG_COLOR = 0  # noir en niveaux de gris


def _pt_to_px(pt: float, dpi: int) -> int:
    """Convertit des points PostScript en pixels entiers."""
    return max(1, round(pt * dpi / _PT_PER_INCH))


def _font_size_px(size_pt: float, dpi: int) -> int:
    """Convertit une taille de police en pt vers des pixels."""
    return max(1, round(size_pt * dpi / _PT_PER_INCH))


class LbxRenderer:
    """
    Convertit un :class:`~lbx.model.LabelLayout` en image PIL monochrome.

    Args:
        font_resolver: Résolveur de polices à utiliser. Si ``None``, une
            instance par défaut de :class:`~lbx.fonts.FontResolver` est créée.
        dpi: Résolution cible en points par pouce. Par défaut 300 DPI
            (résolution native Brother QL).
    """

    def __init__(
        self,
        font_resolver: FontResolver | None = None,
        dpi: int = _DEFAULT_DPI,
    ) -> None:
        self._fonts = font_resolver or FontResolver()
        self.dpi = dpi

    def render(self, layout: LabelLayout) -> Image.Image:
        """
        Rend le layout en image monochrome.

        Args:
            layout: Layout d'étiquette parsé et muté via ``set_field``.

        Returns:
            Image PIL en mode ``"1"`` (monochrome 1 bit), orientée pour
            une impression directe sur Brother QL.

        En mode landscape, le canvas de design est d'abord rendu avec
        les axes inversés (X = longueur bande, Y = largeur bande), puis
        l'image est pivotée de 270° (CW) pour que sa largeur corresponde
        à la largeur physique de la bande, format attendu par brother_ql.
        """
        width_px, height_px = self._canvas_size(layout)

        image = Image.new("L", (width_px, height_px), color=_BG_COLOR)
        draw = ImageDraw.Draw(image)

        for obj in layout.objects.values():
            if isinstance(obj, TextObject):
                self._render_text(
                    draw, obj, layout.paper.margin_left_pt, layout.paper.margin_top_pt
                )
            else:
                logger.debug(
                    "Objet %r de type %r non rendu (non supporté).",
                    obj.object_name,
                    obj.object_type,
                )

        if layout.paper.orientation == "landscape":
            image = image.rotate(270, expand=True)

        return image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    def _canvas_size(self, layout: LabelLayout) -> tuple[int, int]:
        """
        Calcule les dimensions du canvas en pixels.

        Si ``auto_length`` est actif, la dimension de longueur est dérivée
        du contenu (Y en portrait, X en landscape) ; sinon la hauteur
        déclarée dans le XML est utilisée.
        """
        paper = layout.paper

        if paper.orientation == "landscape":
            # X -> longueur (paper.height_pt), Y -> largeur (paper.width_pt)
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
            # Mode portrait standard
            # X -> largeur (paper.width_pt), Y -> longueur (paper.height_pt)
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
            "Canvas (%s) : %d × %d px (%s DPI)",
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
        """
        Dessine un objet texte sur le canvas.

        Applique le shrink si nécessaire, calcule l'alignement, puis
        dessine les lignes (retournées à la ligne selon la bounding-box)
        une par une.
        """
        if not obj.text:
            return

        # Bounding box de l'objet en pixels
        bbox_x = _pt_to_px(margin_left_pt + obj.x_pt, self.dpi)
        bbox_y = _pt_to_px(margin_top_pt + obj.y_pt, self.dpi)
        bbox_w = _pt_to_px(obj.width_pt, self.dpi)
        bbox_h = _pt_to_px(obj.height_pt, self.dpi)

        runs = obj.iter_runs()

        # Résolution des polices avec taille courante
        font_size_pt = self._resolve_font_size(draw, runs, obj, bbox_w, bbox_h)

        # Dessine les lignes
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
        """
        Détermine la taille de police effective.

        Si ``obj.shrink`` est actif, réduit la taille par pas de
        :data:`_SHRINK_STEP_PT` jusqu'à ce que le texte - une fois
        retourné à la ligne selon ``bbox_w`` - tienne dans la
        bounding-box, ou que le minimum soit atteint.

        La taille initiale est le plus petit ``size_pt`` parmi tous les
        runs (Brother stocke déjà le résultat du shrink dans chaque run),
        pas ``obj.default_font.size_pt``.

        Returns:
            Taille en points à utiliser pour le rendu.
        """
        if not obj.shrink:
            return obj.default_font.size_pt

        # Brother stocke déjà le résultat du shrink dans les runs.
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
        """
        Découpe le texte complet en lignes visuelles respectant ``bbox_w``.

        Découpage en deux temps : d'abord sur les retours à la ligne
        explicites (``\\n``), puis mot par mot (espaces) à l'intérieur de
        chaque paragraphe. Un mot à lui seul plus large que ``bbox_w``
        n'est pas coupé - il déborde plutôt que d'être tronqué au milieu.

        En mode normal (pas shrink), chaque run conserve sa propre taille
        de police pour la mesure. En mode shrink, ``size_pt`` est utilisé
        uniformément.

        Args:
            draw:    Contexte de dessin utilisé pour mesurer le texte.
            runs:    Segments ``(texte, police)`` du texte complet.
            size_pt: Taille de police courante (pour la mesure en shrink).
            bbox_w:  Largeur disponible en pixels.
            obj:     Objet texte parent (pour connaître ``shrink``).

        Returns:
            Liste de tuples ``(texte_de_la_ligne, offset_début, offset_fin)``,
            les offsets étant exprimés dans le texte complet reconstitué
            (``"".join(text for text, _ in runs)``), pour permettre de
            retrouver les runs correspondants via
            :meth:`_slice_runs_for_line`.
        """
        full_text = "".join(text for text, _ in runs)

        if obj is not None and not obj.auto_lf:
            return self._wrap_explicit_lines(full_text)

        shrink = obj.shrink if obj is not None else False
        ref_font_spec = runs[0][1] if runs else FontSpec("Arial", size_pt)
        pil_font = self._get_pil_font(
            ref_font_spec,
            size_pt if shrink else None,
        )

        result: list[tuple[str, int, int]] = []
        paragraph_start = 0

        for paragraph in full_text.split("\n"):
            # Précalcule (mot, offset_début, offset_fin) dans full_text.
            words: list[tuple[str, int, int]] = []
            cursor = paragraph_start
            for word in paragraph.split(" "):
                words.append((word, cursor, cursor + len(word)))
                cursor += len(word) + 1  # +1 pour l'espace consommé

            line_words: list[tuple[str, int, int]] = []

            def flush_line(
                words_in_line: list[tuple[str, int, int]],
            ) -> None:
                if not words_in_line:
                    return

                text = " ".join(w for w, _, _ in words_in_line)
                end = words_in_line[-1][2]

                if end < len(full_text) and full_text[end] == " ":
                    end += 1

                result.append((text, words_in_line[0][1], end))

            for word, w_start, w_end in words:
                candidate = line_words + [(word, w_start, w_end)]
                candidate_text = " ".join(w for w, _, _ in candidate)
                bbox = draw.textbbox((0, 0), candidate_text, font=pil_font)
                width = bbox[2] - bbox[0]

                if width <= bbox_w or not line_words:
                    # Ça tient, ou c'est le premier mot de la ligne
                    # (jamais laissé vide - déborde plutôt que rien).
                    line_words = candidate
                else:
                    flush_line(line_words)
                    line_words = [(word, w_start, w_end)]

            flush_line(line_words)
            paragraph_start = cursor  # position juste après le \n consommé

        return result

    def _wrap_explicit_lines(
        self,
        full_text: str,
    ) -> list[tuple[str, int, int]]:
        """
        New line only by \\n. (autoLF=false)
        """

        result = []

        start = 0

        for line in full_text.split("\n"):
            end = start + len(line)

            result.append(
                (
                    line,
                    start,
                    end,
                )
            )

            # skip \n
            start = end + 1

        return result

    def _line_spacing_px(
        self,
        obj: TextObject | None,
        font_size_pt: float,
    ) -> int:
        """
        Calcule l'espacement entre lignes en pixels.

        Même avec ``lineSpace=0``, un leading de base (~25 % de la hauteur
        de la police) est appliqué pour éviter que les lignes ne se touchent.
        Si Brother a défini un ``lineSpace`` supplémentaire, il s'ajoute
        par-dessus.

        Args:
            obj:           Objet texte (peut être ``None``).
            font_size_pt:  Taille de police courante en points.

        Returns:
            Espacement supplémentaire entre deux lignes, en pixels.
        """
        extra = 0

        if obj is not None and obj.line_space:
            extra = _pt_to_px(obj.line_space, self.dpi)

        font_px = _font_size_px(font_size_pt, self.dpi)

        # Leading de base : ~25 % de la hauteur de la police
        # (PIL ne l'ajoute pas automatiquement contrairement à Brother)
        base = round(font_px * 0.25)

        return base + extra

    def _char_spacing_px(self, obj: TextObject | None) -> int:
        """
        Convertit l'espacement de caractère Brother en pixels.

        Brother stocke ``charSpace`` dans le XML comme une valeur en points.
        """
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
        """
        Mesure la largeur et la hauteur totales du texte pour une taille donnée.

        Le texte est d'abord retourné à la ligne (voir :meth:`_wrap_lines`)
        selon ``bbox_w``, puis mesuré ligne par ligne.

        Quand ``obj.shrink`` est actif, ``size_pt`` surcharge la taille
        de chaque run. En mode normal, chaque run conserve sa propre taille.

        Args:
            draw:   Contexte de dessin.
            runs:   Segments ``(texte, police)``.
            size_pt: Taille de police de secours (utilisée si shrink).
            bbox_w: Largeur disponible en pixels.
            obj:    Objet texte parent (pour connaître ``shrink``).

        Returns:
            Tuple ``(largeur_max, hauteur_totale)`` en pixels.
        """
        # shrink = obj.shrink if obj is not None else False
        lines = self._wrap_lines(draw, runs, size_pt, bbox_w, obj)

        max_w = 0
        total_h = 0
        line_spacing = self._line_spacing_px(obj, size_pt)

        for _, _start, _end in lines:
            size_value = size_pt  # size_pt if shrink else None

            line_w = self._measure_line_width(
                draw,
                self._slice_runs_for_line(runs, _start, _end - _start),
                size_value,
                obj,
            )
            line_h = self._measure_line_height(
                draw,
                self._slice_runs_for_line(runs, _start, _end - _start),
                size_value,
            )
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
        """
        Dessine les lignes (retournées à la ligne) en appliquant
        l'alignement horizontal et vertical.

        Chaque ligne peut contenir plusieurs runs (polices différentes) ;
        la position X est avancée run par run. L'alignement vertical
        positionne le bloc de texte dans la bounding-box.

        En mode normal (pas shrink), chaque run conserve sa propre taille
        de police. En mode shrink, ``size_pt`` est utilisé uniformément
        via l'override de ``_get_pil_font``.
        """
        # shrink = obj.shrink
        override = size_pt  # size_pt if shrink else None

        lines = self._wrap_lines(draw, runs, size_pt, bbox_w, obj)

        # Mesure globale pour l'alignement vertical
        _, total_h = self._measure_runs(draw, runs, size_pt, bbox_w, obj)

        # Position Y de départ selon l'alignement vertical
        if obj.v_align == "CENTER":
            start_y = bbox_y + (bbox_h - total_h) // 2
        elif obj.v_align == "BOTTOM":
            start_y = bbox_y + bbox_h - total_h
        else:  # TOP
            start_y = bbox_y

        current_y = start_y
        line_spacing = self._line_spacing_px(obj, size_pt)
        char_spacing = self._char_spacing_px(obj)

        for _, line_start, line_end in lines:
            line_runs = self._slice_runs_for_line(
                runs, line_start, line_end - line_start
            )

            # Mesure de la ligne pour l'alignement horizontal
            line_w = self._measure_line_width(draw, line_runs, override, obj)
            line_h = self._measure_line_height(draw, line_runs, override)

            if obj.h_align == "CENTER":
                start_x = bbox_x + (bbox_w - line_w) // 2
            elif obj.h_align == "RIGHT":
                start_x = bbox_x + bbox_w - line_w
            else:  # LEFT
                start_x = bbox_x

            current_x = start_x

            for run_text, font_spec in line_runs:
                if not run_text:
                    continue

                pil_font = self._get_pil_font(font_spec, override)
                # Compensation du baseline PIL : draw.text positionne
                # le coin supérieur gauche du bounding-box, pas le baseline.
                bbox = draw.textbbox((0, 0), run_text, font=pil_font)
                draw.text(
                    (current_x, current_y - bbox[1]),
                    run_text,
                    font=pil_font,
                    fill=_FG_COLOR,
                )
                current_x += cast(int, bbox[2] - bbox[0] + char_spacing)

            current_y += line_h + line_spacing

    def _slice_runs_for_line(
        self,
        runs: list[tuple[str, FontSpec]],
        line_start: int,
        line_len: int,
    ) -> list[tuple[str, FontSpec]]:
        """
        Extrait les segments de runs correspondant à une ligne de texte.

        Args:
            runs:       Tous les runs du texte complet.
            line_start: Offset de début de la ligne dans le texte complet.
            line_len:   Longueur de la ligne (sans le ``\\n``).

        Returns:
            Liste de tuples ``(texte_du_segment, police)``.
        """
        result: list[tuple[str, FontSpec]] = []
        full_text = "".join(t for t, _ in runs)
        line_text = full_text[line_start : line_start + line_len]

        # Reconstruit les runs pour ce segment de texte
        offset_in_full = 0
        for run_text, font in runs:
            run_start = offset_in_full
            run_end = run_start + len(run_text)
            seg_start = max(run_start, line_start)
            seg_end = min(run_end, line_start + line_len)

            if seg_start < seg_end:
                seg = full_text[seg_start:seg_end]
                result.append((seg, font))

            offset_in_full = run_end

        return result or [(line_text, runs[0][1] if runs else FontSpec("Arial", 10.0))]

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
            # Largeur du texte + espacement entre chaque caractère
            run_w = cast(int, bbox[2] - bbox[0] + char_spacing * len(text))
            total += run_w
        return total

    def _measure_line_height(
        self,
        draw: ImageDraw.ImageDraw,
        line_runs: list[tuple[str, FontSpec]],
        size_pt: float,
    ) -> int:
        """
        Mesure la hauteur de ligne via les métriques de la police.

        Utilise ``getmetrics()`` (ascent + descent) plutôt que
        ``textbbox()``, car ce dernier ne retourne que la hauteur
        visible des glyphes, ce qui sous-estime la hauteur de ligne
        pour des polices comme Atlanta (capitale ~70-80 % du corps).

        Returns:
            Hauteur de ligne en pixels (ascent + descent max des runs).
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
        """
        Résout et retourne la police PIL correspondant à un :class:`FontSpec`.

        Args:
            font_spec:        Spécification de police.
            override_size_pt: Taille à utiliser à la place de
                              ``font_spec.size_pt`` (pour le shrink).
        """
        size_pt = (
            override_size_pt if override_size_pt is not None else font_spec.size_pt
        )
        size_px = _font_size_px(size_pt, self.dpi)

        return self._fonts.resolve(
            name=font_spec.name,
            bold=font_spec.bold,
            italic=font_spec.italic,
            size_px=size_px,
        )
