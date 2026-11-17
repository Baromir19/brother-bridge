"""
Point d'entrée du package ``managers``.

Expose :

- :class:`~managers.label_document.LabelDocument` - contrat abstrait
  commun à toutes les plateformes.
- :func:`document_factory` - fabrique retournant une instance prête à
  l'emploi selon la plateforme courante :

  - Windows -> :class:`~managers.bpac_document.BpacDocument` (SDK b-PAC COM)
  - Autres  -> :class:`~managers.linux_brother_document.LinuxBrotherDocument`
    (pipeline .lbx en mémoire + CUPS)

Les imports de ``BpacDocument`` et ``LinuxBrotherDocument`` sont
intentionnellement *lazy* (effectués à l'intérieur de la fabrique) pour
éviter tout import de dépendances COM (``win32com``, ``pythoncom``) sur
Linux, et inversement.
"""

import platform

from config.settings import settings

from .label_document import LabelDocument


def document_factory() -> LabelDocument:
    """
    Retourne une instance de document d'étiquette adaptée à la plateforme.

    - Windows -> :class:`~managers.bpac_document.BpacDocument`
    - Autres  -> :class:`~managers.linux_brother_document.LinuxBrotherDocument`

    Les imports sont différés pour éviter toute dépendance COM sur Linux.

    Returns:
        Nouvelle instance de :class:`LabelDocument` prête à être utilisée
        comme gestionnaire de contexte.
    """
    if platform.system() == "Windows":
        from .bpac_document import BpacDocument

        return BpacDocument()

    from .linux_brother_document import LinuxBrotherDocument

    return LinuxBrotherDocument(
        host=settings.brother_printer_host, model=settings.brother_printer_model
    )


__all__ = [
    "LabelDocument",
    "document_factory",
]
