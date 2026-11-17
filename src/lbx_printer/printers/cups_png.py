"""CUPS backend that pipes PNG data to ``lp``.

The image is encoded in memory and written to the standard input of ``lp``, so
no temporary file is created. This works with every CUPS queue whose driver
accepts raster images, including the Brother QL drivers.
"""

from __future__ import annotations

import logging
import subprocess
from io import BytesIO

from PIL import Image

from ..exceptions import MissingDependencyError
from .backend import PrinterBackend

logger = logging.getLogger(__name__)

CALL_TIMEOUT_S = 30
"""Timeout for a single ``lp`` invocation, in seconds."""


class CupsPngBackend(PrinterBackend):
    """Send rendered labels to a CUPS queue.

    Args:
        lp_path: ``lp`` executable or absolute path to it.
        timeout: Timeout for the ``lp`` process, in seconds.
    """

    def __init__(self, lp_path: str = "lp", timeout: int = CALL_TIMEOUT_S) -> None:
        self._lp_path = lp_path
        self._timeout = timeout

    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """Encode ``image`` as PNG and submit it with ``lp``.

        Args:
            image: Rendered label.
            printer: CUPS queue name; empty selects the default queue.
            copies: Number of copies.

        Returns:
            ``True`` when ``lp`` exits successfully.

        Raises:
            MissingDependencyError: If ``lp`` is not installed.
            subprocess.CalledProcessError: If ``lp`` rejects the job.
            subprocess.TimeoutExpired: If ``lp`` does not finish in time.
        """
        png_bytes = _encode_png(image)
        command = self.build_command(printer, copies)

        logger.debug(
            "Submitting to CUPS: queue=%r, copies=%d, size=%d bytes",
            printer or "(default)",
            copies,
            len(png_bytes),
        )

        try:
            result = subprocess.run(
                command,
                input=png_bytes,
                capture_output=True,
                timeout=self._timeout,
                check=True,
            )
        except FileNotFoundError as exc:
            raise MissingDependencyError(
                "lp",
                "Install the CUPS client tools (package 'cups-client' on "
                "Debian/Ubuntu, 'cups' on macOS with Homebrew).",
            ) from exc
        except subprocess.CalledProcessError as exc:
            logger.error(
                "'lp' failed with exit code %s. stderr: %s",
                exc.returncode,
                _decode(exc.stderr),
            )
            raise

        for stream, payload in (("stdout", result.stdout), ("stderr", result.stderr)):
            if payload:
                logger.debug("lp %s: %s", stream, _decode(payload))

        return True

    def build_command(self, printer: str, copies: int) -> list[str]:
        """Return the ``lp`` argument list for one job.

        A trailing ``-`` tells ``lp`` to read the document from standard input.

        Args:
            printer: CUPS queue name; empty selects the default queue.
            copies: Number of copies.
        """
        command = [self._lp_path]

        if printer:
            command += ["-d", printer]

        if copies > 1:
            command += ["-n", str(copies)]

        command.append("-")

        return command


def _encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def _decode(payload: bytes | None) -> str:
    return (payload or b"").decode(errors="replace").strip()


__all__ = ["CALL_TIMEOUT_S", "CupsPngBackend"]
