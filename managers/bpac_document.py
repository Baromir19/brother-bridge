"""
Implémentation Windows du gestionnaire de documents d'étiquettes.

Utilise le SDK Brother b-PAC via COM (win32com). Ce module ne doit
être importé que sur Windows - les imports COM sont effectués de
manière lazy à l'intérieur des méthodes pour éviter tout échec
au chargement du module sur les autres plateformes.
"""

import logging
from pathlib import Path
from typing import Any

from ..exceptions import (
    BpacConnectionError,
    LabelFieldNotFoundError,
    LabelTemplateNotFoundError,
)
from ..models import PrintMode
from .label_document import LabelDocument

logger = logging.getLogger(__name__)


class BpacDocument(LabelDocument):
    """
    Gestionnaire de documents b-PAC pour Windows.

    Encapsule l'API COM ``bpac.Document`` du SDK Brother. Doit être
    utilisé exclusivement via le protocole de gestionnaire de contexte
    afin de garantir la libération du thread COM ::

        with BpacDocument() as doc:
            doc.open(template_path)
            doc.set_field("reference", "REF-001")
            doc.print(copies=2)
    """

    def __init__(self) -> None:
        self._doc: Any = None

    def _initialize(self) -> None:
        """
        Initialise le thread COM et crée l'objet ``bpac.Document``.

        Raises:
            BpacConnectionError: Si le SDK b-PAC n'est pas installé ou
                si la création de l'objet COM échoue.
        """
        import pythoncom
        import win32com.client

        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)

        try:
            doc = win32com.client.DispatchEx("bpac.Document")

            if doc is None:
                raise ValueError("bpac.Document est None après DispatchEx")

            self._doc = doc

        except Exception as e:
            pythoncom.CoUninitialize()

            raise BpacConnectionError(
                f"Erreur d'initialisation de b-PAC : {e}. "
                "Vérifiez que le SDK Brother b-PAC est bien installé."
            ) from e

    def close(self) -> None:
        """
        Ferme le document et libère le thread COM.

        Appelé automatiquement par ``__exit__``. Ne lève jamais
        d'exception afin de ne pas masquer une éventuelle erreur
        métier survenue dans le bloc ``with``.
        """
        try:
            # if self._doc is not None:
            #    self._doc.Close()
            pass

        except Exception:
            logger.warning("Échec de la fermeture du document b-PAC.", exc_info=True)

        finally:
            import pythoncom

            pythoncom.CoUninitialize()
            self._doc = None

    def _open(self, path: Path) -> None:
        """
        Ouvre le modèle d'étiquette via l'API b-PAC.

        Le fichier est validé en amont par ``LabelDocument.open``.

        Args:
            path: Chemin validé vers le fichier modèle .lbx.

        Raises:
            LabelTemplateNotFoundError: Si b-PAC refuse d'ouvrir le fichier.
        """
        if not self._doc.Open(str(path)):
            raise LabelTemplateNotFoundError(
                f"b-PAC ne peut pas ouvrir le fichier modèle : {path}"
            )

    def _set_field(self, name: str, value: str) -> None:
        """
        Définit la valeur d'un champ texte via l'API b-PAC.

        Args:
            name:  Identifiant du champ dans le modèle.
            value: Valeur textuelle à afficher sur l'étiquette.

        Raises:
            LabelFieldNotFoundError: Si le champ est absent du modèle.
        """
        obj = self._doc.GetObject(name)

        if obj is None:
            raise LabelFieldNotFoundError(
                f"Champ introuvable dans le modèle d'étiquette : {name!r}"
            )

        obj.Text = value

    def print(self, copies: int = 1, printer: str = "") -> bool:
        """
        Lance l'impression via le SDK b-PAC.

        Args:
            copies:  Nombre d'exemplaires à imprimer.
            printer: Nom de l'imprimante cible (chaîne vide = défaut système).

        Returns:
            ``True`` si l'impression a réussi, ``False`` sinon.
        """
        # StartPrint(nom_travail, mode) - 0 = b_Print_Default
        self._doc.StartPrint(printer, PrintMode.NORMAL)

        # PrintOut(copies, mode)
        result = self._doc.PrintOut(copies, PrintMode.NORMAL)

        # self._doc.EndPrint

        return bool(result)
