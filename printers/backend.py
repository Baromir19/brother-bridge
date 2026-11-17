"""
Contrat abstrait pour les backends d'impression.

Sépare la logique de rendu de la logique d'envoi vers l'imprimante.
Chaque backend reçoit une image PIL déjà rendue et est responsable
uniquement de son acheminement vers le périphérique physique.

Implémentations disponibles :

- :class:`~printers.cups_png.CupsPngBackend` - envoie un PNG sur stdin
  de ``lp`` (CUPS), sans fichier temporaire.

Implémentations futures envisagées :

- ``BrotherRasterBackend`` - envoi direct en format rastérisé Brother
  via la bibliothèque ``brother_ql``.
- ``FileBackend`` - sauvegarde dans un fichier (tests, debug).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class PrinterBackend(ABC):
    """
    Interface d'envoi d'une image rendue vers une imprimante physique.

    Les implémentations ne doivent pas écrire de fichier temporaire sauf
    contrainte absolue documentée.
    """

    @abstractmethod
    def print(
        self,
        image: Image.Image,
        printer: str,
        copies: int = 1,
    ) -> bool:
        """
        Envoie l'image vers l'imprimante.

        Args:
            image:   Image PIL à imprimer (généralement monochrome ``"1"``).
            printer: Nom de la file d'attente CUPS ou identifiant
                     d'imprimante. Une chaîne vide signifie l'imprimante
                     par défaut du système.
            copies:  Nombre d'exemplaires à imprimer.

        Returns:
            ``True`` si l'envoi a réussi.
        """
