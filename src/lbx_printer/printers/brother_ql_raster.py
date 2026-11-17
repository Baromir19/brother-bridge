"""Direct raster backend for Brother QL printers.

The image is converted to Brother's raster command language and streamed over
TCP to the printer, without CUPS or a vendor driver. The device receives exactly
the pixels produced by the renderer; no intermediate scaling is applied.

Requires the ``brother_ql`` distribution (installed as a dependency) and a
printer reachable on the network (JetDirect port 9100 by default).
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from ..exceptions import MissingDependencyError
from .backend import PrinterBackend

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9100
"""Raw TCP port used by network Brother QL printers."""

DEFAULT_THRESHOLD = 70.0
"""Black/white threshold in percent when dithering is disabled."""

_MISSING_HINT = (
    "Install the brother_ql distribution: "
    "pip install 'brother-ql @ git+https://github.com/pklaus/brother_ql.git'"
)


def _import_brother_ql() -> tuple[Any, Any, Any]:
    """Import the ``brother_ql`` helpers lazily with an actionable error."""
    try:
        from brother_ql.backends.helpers import send
        from brother_ql.conversion import convert
        from brother_ql.raster import BrotherQLRaster
    except ImportError as exc:
        raise MissingDependencyError("brother_ql", _MISSING_HINT) from exc

    return send, convert, BrotherQLRaster


class BrotherQlRasterBackend(PrinterBackend):
    """Convert rendered labels to Brother raster data and send them by TCP.

    Args:
        host: Printer address, e.g. ``"192.168.1.50"``.
        model: Model name understood by ``brother_ql``, e.g. ``"QL-1110NWB"``.
        label: ``brother_ql`` label identifier, e.g. ``"62"`` for continuous
            62 mm tape or ``"103x164"`` for a die-cut label.
        port: TCP port of the printer.
        cut: Cut the tape after each copy.
        threshold: Threshold in percent used when ``dither`` is false.
        dither: Dither the image instead of thresholding it. Text rendered in
            pure black does not need dithering.

    Note:
        The ``printer`` argument of :meth:`print` is ignored: this backend talks
        to the address given by ``host`` (and ``port``).
    """

    def __init__(
        self,
        host: str,
        model: str,
        label: str,
        port: int = DEFAULT_PORT,
        cut: bool = True,
        threshold: float = DEFAULT_THRESHOLD,
        dither: bool = False,
    ) -> None:
        self.host = host
        self.model = model
        self.label = label
        self.port = port
        self.cut = cut
        self.threshold = threshold
        self.dither = dither

    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """Send ``copies`` of ``image`` to the configured printer.

        Args:
            image: Rendered label, any Pillow mode.
            printer: Ignored; see the class note.
            copies: Number of copies, each sent as a separate label in the job.

        Returns:
            ``True`` when the data was transmitted.

        Raises:
            MissingDependencyError: If ``brother_ql`` is not installed.
            Exception: Any error raised by ``brother_ql`` (invalid model or
                label, network failure) is propagated unchanged.
        """
        send, convert, brother_ql_raster = _import_brother_ql()

        raster = brother_ql_raster(self.model)
        raster.exception_on_warning = True

        flat_image = image.convert("L")
        instructions = convert(
            qlr=raster,
            images=[flat_image] * max(1, copies),
            label=self.label,
            threshold=self.threshold,
            dither=self.dither,
            cut=self.cut,
        )

        target = f"tcp://{self.host}:{self.port}"
        logger.debug(
            "Sending %d byte(s) of raster data to %s (model=%s, label=%s, copies=%d)",
            len(instructions),
            target,
            self.model,
            self.label,
            copies,
        )

        send(
            instructions=instructions,
            printer_identifier=target,
            backend_identifier="network",
            blocking=True,
        )

        return True


__all__ = ["DEFAULT_PORT", "DEFAULT_THRESHOLD", "BrotherQlRasterBackend"]
