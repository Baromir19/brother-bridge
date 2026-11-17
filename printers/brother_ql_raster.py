"""
Backend d'impression directe en raster Brother, sans CUPS.

Contrairement à :class:`~printers.cups_png.CupsPngBackend`, ce backend
ne dépend d'aucun pilote système ni filtre CUPS : l'image PIL est
convertie en instructions raster propriétaires Brother, puis envoyée
en flux brut sur le réseau (ou USB). Aucune mise à l'échelle
implicite n'est appliquée par une couche intermédiaire.

Prérequis
---------
- ``brother_ql`` doit être installé (voir ``pyproject.toml``).
- L'imprimante doit être accessible sur le réseau (port 9100 par défaut).
"""

from __future__ import annotations

import logging
from pathlib import Path

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

from .backend import PrinterBackend

logger = logging.getLogger(__name__)

# Port raw/JetDirect standard pour l'impression réseau (Brother QL WiFi).
_DEFAULT_PORT = 9100


class BrotherQlRasterBackend(PrinterBackend):
    """
    Backend d'impression directe en raster Brother, sans CUPS.

    Contrairement à :class:`~printers.cups_png.CupsPngBackend`, ce backend
    ne dépend d'aucun pilote système ni filtre CUPS : l'image PIL est
    convertie en instructions raster propriétaires Brother, puis envoyée
    en flux brut sur le réseau (ou USB). Aucune mise à l'échelle
    implicite n'est appliquée par une couche intermédiaire.

    Args:
        host:      Adresse IP de l'imprimante réseau
                   (ex. ``"192.168.1.50"``).
        model:     Modèle exact, tel qu'attendu par ``brother_ql``
                   (ex. ``"QL-820NWB"``, ``"QL-800"``...).
        label:     Identifiant de bande/étiquette brother_ql
                   (ex. ``"62"`` pour une bande continue 62 mm).
                   Voir ``brother_ql info labels`` pour la liste complète
                   et les dimensions en pixels attendues.
        port:      Port TCP de l'imprimante réseau (9100 par défaut).
        cut:       Coupe automatique après impression.
        threshold: Seuil noir/blanc en % si l'image n'est pas déjà
                   strictement monochrome. Sans effet si ``dither=True``.
        dither:    Tramage au lieu d'un seuil fixe (utile pour des photos,
                   inutile pour du texte déjà rendu en noir pur par
                   :class:`~lbx.renderer.LbxRenderer`).
    """

    def __init__(
        self,
        host: str,
        model: str,
        label: str,
        port: int = _DEFAULT_PORT,
        cut: bool = True,
        threshold: float = 70.0,
        dither: bool = False,
    ) -> None:
        self._host = host
        self._model = model
        self._label = label
        self._port = port
        self._cut = cut
        self._threshold = threshold
        self._dither = dither

    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """
        Convertit l'image en raster Brother et l'envoie sur le réseau.

        Args:
            image:   Image PIL à imprimer (mode ``"1"`` attendu depuis
                     :class:`~lbx.renderer.LbxRenderer`, mais tout mode
                     PIL est accepté).
            printer: Adresse IP à utiliser à la place de ``host`` si non
                     vide (permet de surcharger ponctuellement la cible ;
                     ``paper.printer_name`` du XML n'est PAS utilisable
                     ici, voir note du module).
            copies:  Nombre d'exemplaires. Chaque exemplaire est envoyé
                     comme une étiquette distincte dans le même job, avec
                     coupe entre chaque si ``cut=True``.

        Returns:
            ``True`` si l'envoi a réussi.

        Raises:
            Toute exception levée par ``brother_ql`` (modèle/label
            invalide, échec de connexion réseau, etc.) est propagée
            telle quelle - pas de capture silencieuse.
        """
        target_host = self._host

        qlr = BrotherQLRaster(self._model)
        qlr.exception_on_warning = True

        # brother_ql binarise lui-même l'image (seuil ou tramage) ; le
        # mode "1" produit par LbxRenderer passe sans problème, mais on
        # repasse en niveaux de gris pour rester sur un chemin de code
        # éprouvé par la bibliothèque.
        flat_image = image.convert("L")

        instructions = convert(
            qlr=qlr,
            images=[flat_image] * max(1, copies),
            label=self._label,
            threshold=self._threshold,
            dither=self._dither,
            cut=self._cut,
        )

        # Dump de debug, comme pour l'ancien backend CUPS.
        # Inspectable avec : brother_ql analyze /tmp/label_debug.bin
        debug_file = Path("/tmp/label_debug.bin")
        debug_file.write_bytes(instructions)
        logger.info(
            "Instructions raster sauvegardées dans %s (%d octets)",
            debug_file,
            len(instructions),
        )

        logger.debug(
            "Envoi raster -> %s:%d, modèle=%s, bande=%s, copies=%d",
            target_host,
            self._port,
            self._model,
            self._label,
            copies,
        )

        send(
            instructions=instructions,
            printer_identifier=f"tcp://{target_host}:{self._port}",
            backend_identifier="network",
            blocking=True,
        )

        return True
