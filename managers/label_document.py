"""
Contrat abstrait pour les gestionnaires de documents d'étiquettes.

Toute implémentation concrète (b-PAC, LBX, …) doit hériter de
``LabelDocument`` et implémenter les méthodes marquées ``@abstractmethod``.

Patron de conception utilisé : Template Method.
- ``open`` et ``set_field`` contiennent la logique commune (validation,
  normalisation) et délèguent la partie plateforme à ``_open`` /
  ``_set_field``.
- ``__enter__`` / ``__exit__`` sont implémentés une seule fois ici.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Any

from ..exceptions import LabelTemplateNotFoundError


class LabelDocument(ABC):
    """
    Classe de base abstraite pour les documents d'étiquettes.

    Utilisation prévue via le protocole de gestionnaire de contexte ::

        with document_factory() as doc:
            doc.open(template_path)
            doc.set_field("reference", "REF-001")
            doc.print(copies=2)
    """

    def __enter__(self) -> "LabelDocument":
        self._initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def open(self, path: str | Path) -> None:
        """
        Ouvre un fichier de modèle d'étiquette.

        Vérifie l'existence du fichier avant de déléguer à ``_open``.

        Args:
            path: Chemin vers le fichier modèle (relatif ou absolu).

        Raises:
            LabelTemplateNotFoundError: Si le fichier est introuvable.
        """
        resolved = Path(path)

        if not resolved.exists():
            raise LabelTemplateNotFoundError(resolved)

        self._open(resolved)

    def set_field(self, name: str, value: Any) -> None:
        """
        Définit la valeur d'un champ dans le modèle d'étiquette.

        Convertit ``value`` en chaîne avant de déléguer à ``_set_field``.

        Args:
            name:  Identifiant du champ dans le modèle.
            value: Valeur à afficher (sera convertie en ``str``).
        """
        self._set_field(name, str(value))

    @abstractmethod
    def _initialize(self) -> None:
        """
        Initialise les ressources propres à la plateforme.

        Appelé automatiquement par ``__enter__``. Implémentation par
        défaut : aucune action. Les sous-classes qui nécessitent une
        initialisation (ex. COM, connexion SDK) doivent surcharger
        cette méthode.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Libère les ressources propres à la plateforme.

        Appelé automatiquement par ``__exit__``. Implémentation par
        défaut : aucune action. Les sous-classes qui gèrent des
        ressources (ex. COM, fichiers) doivent surcharger cette méthode.
        """
        pass

    @abstractmethod
    def _open(self, path: Path) -> None:
        """
        Ouvre le modèle d'étiquette au niveau de la plateforme.

        Args:
            path: Chemin validé et résolu vers le fichier modèle.
        """
        pass

    @abstractmethod
    def _set_field(self, name: str, value: str) -> None:
        """
        Définit un champ dans le document au niveau de la plateforme.

        Args:
            name:  Identifiant du champ.
            value: Valeur déjà convertie en ``str``.
        """
        pass

    @abstractmethod
    def print(self, copies: int = 1, printer: str = "") -> bool:
        """
        Lance l'impression de l'étiquette.

        Args:
            copies:  Nombre d'exemplaires à imprimer.
            printer: Nom de l'imprimante cible (chaîne vide = défaut).

        Returns:
            ``True`` si l'impression a réussi, ``False`` sinon.
        """
        pass
