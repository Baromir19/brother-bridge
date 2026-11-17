"""Backend that writes rendered labels to image files.

Typical uses are previews in a user interface, visual regression checks and
debugging a printer setup without hardware.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import Image

from .backend import PrinterBackend

logger = logging.getLogger(__name__)

_FORMATS = {"PNG": "png", "BMP": "bmp", "JPEG": "jpg"}


class FileBackend(PrinterBackend):
    """Save every copy as an image file in a directory.

    Args:
        output_dir: Directory that receives the images. Created on first use.
        prefix: File name prefix.
        image_format: One of ``"PNG"``, ``"BMP"`` or ``"JPEG"``.

    Raises:
        ValueError: If ``image_format`` is not supported.

    Example:
        >>> backend = FileBackend(Path("output"), prefix="address")
        >>> backend.print(image, printer="", copies=1)
        True
    """

    def __init__(
        self,
        output_dir: str | Path,
        prefix: str = "label",
        image_format: str = "PNG",
    ) -> None:
        normalised = image_format.upper()

        if normalised not in _FORMATS:
            raise ValueError(f"Unsupported image format: {image_format}")

        self._output_dir = Path(output_dir)
        self._prefix = prefix
        self._image_format = normalised
        self._extension = _FORMATS[normalised]

    @property
    def output_dir(self) -> Path:
        """Directory that receives the rendered images."""
        return self._output_dir

    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """Write one file per copy and return ``True``."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")

        for index in range(1, max(1, copies) + 1):
            path = (
                self._output_dir
                / f"{self._prefix}_{stamp}_{index:03d}.{self._extension}"
            )
            image.save(path, format=self._image_format)
            logger.debug("Label written to %s", path)

        return True


__all__ = ["FileBackend"]
