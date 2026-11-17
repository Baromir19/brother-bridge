"""Contract for components that deliver a rendered image to a printer.

The interface separates rendering from transport: a backend receives an image
that is already rasterised and only decides how to move the pixels to the
device (network raster stream, CUPS queue, file on disk, ...).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class PrinterBackend(ABC):
    """Deliver a rendered label to a physical destination.

    Implementations must be stateless with respect to individual jobs so that a
    single instance can be reused, and must not create temporary files unless
    that is the documented purpose of the backend.
    """

    @abstractmethod
    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """Send ``image`` to the destination.

        Args:
            image: Rendered label, usually a monochrome ``"1"`` image.
            printer: Queue name, device identifier or an empty string for the
                destination default.
            copies: Number of copies to print.

        Returns:
            ``True`` when the job was accepted.
        """


__all__ = ["PrinterBackend"]
