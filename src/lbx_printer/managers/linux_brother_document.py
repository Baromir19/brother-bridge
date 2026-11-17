"""Document manager for Linux and macOS, based on the in-memory pipeline.

The template is parsed once, transformed in memory and rendered to an image
before being handed to a print backend::

    .lbx bytes -> LbxParser -> LabelLayout -> LbxRenderer -> PIL.Image -> backend

Nothing is written to disk. The ``brother_ql`` tape identifier is resolved from
the paper geometry, so templates from any P-touch Editor installation work
without a manual format table.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image

from ..config import DEFAULT_DPI, DEFAULT_HOST, DEFAULT_MODEL
from ..exceptions import MissingDependencyError, PrinterStateError
from ..i18n import translate
from ..lbx.model import LabelLayout, TextObject
from ..lbx.parser import LbxParser
from ..lbx.renderer import LbxRenderer
from ..printers.backend import PrinterBackend
from ..printers.brother_ql_raster import BrotherQlRasterBackend
from ..printers.label_resolver import BrotherQlLabelResolver
from .label_document import LabelDocument

logger = logging.getLogger(__name__)

_MISSING_HINT = (
    "Install the brother_ql distribution: "
    "pip install 'brother-ql @ git+https://github.com/pklaus/brother_ql.git'"
)


@dataclass(frozen=True, slots=True)
class TapeSpec:
    """Printable area and shape of a resolved tape.

    Attributes:
        dots_printable: Printable size in dots, ``(width, height)``.
        die_cut: ``True`` for die-cut labels, which are cropped to the printable
            area, and ``False`` for continuous tape.
    """

    dots_printable: tuple[int, int]
    die_cut: bool


@cache
def default_tape_spec(identifier: str) -> TapeSpec:
    """Read the printable geometry of ``identifier`` from ``brother_ql``.

    Raises:
        MissingDependencyError: If ``brother_ql`` is not installed.
        KeyError: If the identifier is unknown to ``brother_ql``.
    """
    try:
        from brother_ql.labels import FormFactor, LabelsManager
    except ImportError as exc:
        raise MissingDependencyError("brother_ql", _MISSING_HINT) from exc

    specs = LabelsManager().get_label_by_identifier(identifier)
    width, height = specs.dots_printable

    return TapeSpec(
        dots_printable=(width, height),
        die_cut=specs.form_factor in (FormFactor.DIE_CUT, FormFactor.ROUND_DIE_CUT),
    )


class LinuxBrotherDocument(LabelDocument):
    """Print labels on Linux and macOS without a vendor driver.

    Every collaborator is injectable, which allows running the whole pipeline
    without hardware, CUPS or ``brother_ql``::

        doc = LinuxBrotherDocument(
            renderer=FakeRenderer(),
            backend=FakeBackend(),
            tape_spec_provider=lambda _: TapeSpec((696, 200), die_cut=False),
        )

    Args:
        renderer: Layout-to-image renderer. Defaults to :class:`LbxRenderer` at
            ``dpi``.
        backend: Print backend. Defaults to a :class:`BrotherQlRasterBackend`
            built from ``host``, ``model`` and the resolved tape.
        parser: Template parser. Defaults to :class:`LbxParser`.
        label_resolver: Tape resolver. Defaults to
            :class:`BrotherQlLabelResolver`.
        tape_spec_provider: Callable returning the :class:`TapeSpec` of a tape
            identifier. Defaults to :func:`default_tape_spec`.
        host: Printer address used by the default backend.
        model: Printer model used by the default backend.
        label: Explicit tape identifier. When omitted, the tape is resolved from
            the template geometry.
        dpi: Resolution used by the default renderer.
    """

    def __init__(
        self,
        renderer: LbxRenderer | None = None,
        backend: PrinterBackend | None = None,
        parser: LbxParser | None = None,
        label_resolver: BrotherQlLabelResolver | None = None,
        tape_spec_provider: Callable[[str], TapeSpec] | None = None,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        label: str | None = None,
        dpi: int = DEFAULT_DPI,
    ) -> None:
        self._renderer = renderer or LbxRenderer(dpi=dpi)
        self._parser = parser or LbxParser()
        self._label_resolver = label_resolver or BrotherQlLabelResolver()
        self._tape_spec_provider = tape_spec_provider or default_tape_spec
        self._backend_override = backend
        self._host = host
        self._model = model
        self._override_label = label
        self._layout: LabelLayout | None = None
        self._resolved_label: str | None = None

    @property
    def resolved_label(self) -> str | None:
        """Tape identifier resolved at :meth:`_open` time, if any."""
        return self._resolved_label

    @property
    def host(self) -> str:
        """Printer address used by the default backend."""
        return self._host

    @property
    def model(self) -> str:
        """Printer model used by the default backend."""
        return self._model

    def _initialize(self) -> None:
        self._layout = None
        self._resolved_label = None

    def _open(self, path: Path) -> None:
        self._layout = self._parser.parse(path.read_bytes())
        self._resolved_label = (
            self._override_label
            if self._override_label
            else self._label_resolver.resolve(self._layout.paper)
        )

        logger.debug(
            "Template loaded: %s (%d object(s), tape=%r, format_id=%d, printer=%r)",
            path.name,
            len(self._layout.objects),
            self._resolved_label,
            self._layout.paper.format_id,
            self._layout.paper.printer_name,
        )

    def _set_field(self, name: str, value: str) -> None:
        if self._layout is None:
            raise PrinterStateError()

        obj = self._layout.get_object(name)

        if not isinstance(obj, TextObject):
            raise TypeError(
                translate(
                    "invalid_field_type",
                    name=name,
                    object_type=obj.object_type,
                )
            )

        obj.set_text(value)
        logger.debug("Field updated: %r = %r", name, value)

    def print(self, copies: int = 1, printer: str = "") -> bool:
        """Render the label and submit it to the backend.

        The target is chosen in this order: ``printer``, the printer stored in
        the template, the platform default.

        Args:
            copies: Number of copies.
            printer: Printer or queue name.

        Returns:
            ``True`` when the backend accepted the job.

        Raises:
            PrinterStateError: If called before :meth:`open`.
        """
        if self._layout is None:
            raise PrinterStateError()

        if self._resolved_label is None:
            raise PrinterStateError(translate("label_not_resolved"))

        effective_printer = printer or self._layout.paper.printer_name
        image = self._renderer.render(self._layout)
        image = _fit_to_printable(image, self._tape_spec_provider(self._resolved_label))

        logger.debug(
            "Rendering to printer %r with tape %r, %d copy(ies).",
            effective_printer or "(default)",
            self._resolved_label,
            copies,
        )

        backend = self._backend_override or BrotherQlRasterBackend(
            host=self._host,
            model=self._model,
            label=self._resolved_label,
        )

        return backend.print(image=image, printer=effective_printer, copies=copies)


def _fit_to_printable(image: Image.Image, spec: TapeSpec) -> Image.Image:
    """Crop a die-cut label to its printable area, centred.

    Continuous tape keeps its full length and is converted to grayscale, which is
    the input format expected by the raster backends.
    """
    if not spec.die_cut:
        return image.convert("L")

    width, height = spec.dots_printable
    delta_x = image.width - width
    delta_y = image.height - height

    if delta_x < 0 or delta_y < 0:
        logger.warning(
            "Rendered image %sx%s px is smaller than the printable area %sx%s px; "
            "keeping the full image.",
            image.width,
            image.height,
            width,
            height,
        )
        return image.convert("L")

    left = delta_x // 2
    top = delta_y // 2

    cropped = image.crop(
        (left, top, image.width - (delta_x - left), image.height - (delta_y - top))
    )
    logger.debug(
        "Cropped to the printable area: %s px (tape %s).",
        spec.dots_printable,
        "die-cut",
    )

    return cropped


__all__ = ["LinuxBrotherDocument", "TapeSpec", "default_tape_spec"]
