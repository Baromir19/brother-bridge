"""
Package ``printers`` - backends d'impression et résolveur de bandes.

Expose le contrat abstrait :class:`~printers.backend.PrinterBackend`
et les implémentations disponibles :

- :class:`~printers.cups_png.CupsPngBackend` - envoie un PNG sur stdin
  de ``lp`` (CUPS), sans fichier temporaire.
- :class:`~printers.brother_ql_raster.BrotherQlRasterBackend` - envoi
  direct en format rastérisé Brother via la bibliothèque ``brother_ql``,
  sans dépendre de CUPS.

Résolveur de bande :

- :class:`~printers.label_resolver.BrotherQlLabelResolver` - résout
  automatiquement le nom de bande brother_ql à partir des dimensions
  en points PostScript du XML .lbx, sans table de correspondance
  hardcodée.
"""

from .backend import PrinterBackend
from .brother_ql_raster import BrotherQlRasterBackend
from .cups_png import CupsPngBackend
from .label_resolver import BrotherQlLabelResolver, UnsupportedLabelError

__all__ = [
    "PrinterBackend",
    "BrotherQlRasterBackend",
    "CupsPngBackend",
    "BrotherQlLabelResolver",
    "UnsupportedLabelError",
]
