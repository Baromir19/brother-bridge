"""
Backend d'impression CUPS via PNG sur stdin.

Encode l'image PIL en PNG dans un buffer mémoire, puis l'envoie sur
l'entrée standard de ``lp``. Aucun fichier temporaire n'est créé.

Pipeline d'envoi ::

    PIL.Image
        │
        │  image.save(buffer, format="PNG")
        ▼
    BytesIO (PNG bytes en RAM)
        │
        │  subprocess.run(["lp", ...], input=bytes)
        ▼
    lp stdin
        │
        ▼
    CUPS
        │
        ▼
    Brother QL

Prérequis système
-----------------
- ``lp`` doit être disponible dans le ``PATH`` (paquet ``cups-client``).
- L'utilisateur doit avoir les droits d'impression (groupe ``lpadmin``
  ou équivalent selon la distribution).
"""

from __future__ import annotations

import logging
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

from .backend import PrinterBackend

logger = logging.getLogger(__name__)

# Timeout d'envoi à CUPS en secondes.
# Sur un réseau local avec un Brother QL, 30 s est largement suffisant.
_CUPS_TIMEOUT_S = 30


class CupsPngBackend(PrinterBackend):
    """
    Backend CUPS : envoie une image PNG sur stdin de ``lp``.

    Args:
        lp_path: Chemin vers l'exécutable ``lp``. Par défaut ``"lp"``
            (résolu depuis le ``PATH``).
        timeout: Délai d'attente en secondes pour le processus ``lp``.
    """

    def __init__(
        self,
        lp_path: str = "lp",
        timeout: int = _CUPS_TIMEOUT_S,
    ) -> None:
        self._lp_path = lp_path
        self._timeout = timeout

    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """
        Encode l'image en PNG et l'envoie à CUPS via ``lp``.

        Args:
            image:   Image PIL à imprimer.
            printer: Nom de la file CUPS. Si vide, ``lp`` utilise
                     l'imprimante par défaut.
            copies:  Nombre d'exemplaires.

        Returns:
            ``True`` si ``lp`` s'est terminé avec le code de retour 0.

        Raises:
            subprocess.CalledProcessError: Si ``lp`` retourne un code
                d'erreur non nul.
            FileNotFoundError: Si ``lp`` est introuvable dans le PATH.
            subprocess.TimeoutExpired: Si l'envoi dépasse :attr:`_timeout`.
        """
        png_bytes = self._encode_png(image)
        cmd = self._build_command(printer, copies)

        logger.debug(
            "Envoi vers CUPS : imprimante=%r, copies=%d, taille=%d octets",
            printer or "(défaut)",
            copies,
            len(png_bytes),
        )

        debug_file = Path("/tmp/label_debug.png")
        debug_file.write_bytes(png_bytes)

        logger.info("PNG saved to %s", debug_file)
        logger.info("PNG size: %d bytes", len(png_bytes))

        try:
            result = subprocess.run(
                cmd,
                input=png_bytes,
                capture_output=True,
                timeout=self._timeout,
                check=True,
            )

            if result.stdout:
                logger.debug("lp stdout: %s", result.stdout.decode(errors="replace"))

            if result.stderr:  # or stdout
                logger.debug("lp stderr: %s", result.stderr.decode(errors="replace"))

        except subprocess.CalledProcessError as exc:
            logger.error("lp command failed")
            logger.error("returncode: %s", exc.returncode)
            logger.error("stdout: %s", exc.stdout.decode(errors="replace"))
            logger.error("stderr: %s", exc.stderr.decode(errors="replace"))
            raise

        return True

    @staticmethod
    def _encode_png(image: Image.Image) -> bytes:
        """
        Encode l'image PIL en PNG dans un buffer mémoire.

        Args:
            image: Image source (tout mode PIL accepté).

        Returns:
            Bytes PNG.
        """
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _build_command(self, printer: str, copies: int) -> list[str]:
        """
        Construit la commande ``lp``.

        ``-`` en fin de commande indique à ``lp`` de lire depuis stdin.

        Args:
            printer: Nom de la file CUPS (vide = défaut système).
            copies:  Nombre d'exemplaires.

        Returns:
            Liste d'arguments pour ``subprocess.run``.
        """
        cmd: list[str] = [self._lp_path]

        if printer:
            cmd += ["-d", printer]

        if copies > 1:
            cmd += ["-n", str(copies)]

        cmd.append("-")  # lire depuis stdin

        return cmd
