"""
Service de haut niveau pour l'impression d'étiquettes.

Ce module ne connaît aucune implémentation concrète de document.
Il travaille uniquement avec le contrat :class:`LabelDocument` via
une fabrique injectable - ce qui rend le service testable sur toute
plateforme sans dépendance COM.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from ..exceptions import LabelDataMissingError, LabelTemplateNotFoundError
from ..managers import LabelDocument
from ..managers import document_factory as _default_factory
from ..models import PrintRequest

logger = logging.getLogger(__name__)


class LabelPrinterService:
    """
    Service d'impression d'étiquettes indépendant de la plateforme.

    La dépendance au document concret est injectée via ``document_factory``,
    ce qui permet de substituer n'importe quelle implémentation de
    :class:`LabelDocument` - notamment en test ::

        service = LabelPrinterService(
            template_dir=Path("templates"),
            document_factory=lambda: FakeDocument(),
        )

    En production, la fabrique par défaut sélectionne automatiquement
    l'implémentation adaptée à la plateforme courante.
    """

    def __init__(
        self,
        template_dir: Path,
        document_factory: Callable[[], LabelDocument] | None = None,
    ) -> None:
        """
        Initialise le service d'impression.

        Args:
            template_dir:      Répertoire racine contenant les fichiers
                               modèles d'étiquettes.
            document_factory:  Fabrique retournant une instance de
                               :class:`LabelDocument`. Si ``None``,
                               la fabrique par défaut est utilisée
                               (:func:`managers.document_factory`,
                               sélection automatique selon la plateforme).
        """
        self.template_dir = template_dir

        self._document_factory = (
            document_factory if document_factory is not None else _default_factory
        )

    def print_label(self, request: PrintRequest) -> bool:
        """
        Imprime une étiquette à partir d'une requête d'impression.

        Args:
            request: Requête contenant le modèle, les données et les
                     paramètres d'impression.

        Returns:
            ``True`` si l'impression a réussi.

        Raises:
            LabelTemplateNotFoundError: Si le fichier modèle est absent.
            LabelDataMissingError:      Si des champs obligatoires manquent.
        """
        template_path = self.template_dir / request.label.template

        if not template_path.exists():
            raise LabelTemplateNotFoundError(
                f"Fichier modèle introuvable dans le répertoire : {template_path}"
            )

        self._validate(request)

        with self._document_factory() as doc:
            doc.open(template_path)

            for name, value in request.data.values.items():
                doc.set_field(name, value)

            return doc.print(copies=request.copies, printer=request.printer)

    def _validate(self, request: PrintRequest) -> None:
        """
        Vérifie que tous les champs obligatoires du modèle sont fournis.

        Args:
            request: Requête d'impression à valider.

        Raises:
            LabelDataMissingError: Si des champs déclarés dans le modèle
                sont absents des données fournies.
        """
        missing = set(request.label.fields) - set(request.data.values.keys())

        if missing:
            raise LabelDataMissingError(
                f"Données manquantes pour les champs du modèle : {missing}"
            )
