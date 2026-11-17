class PrinterError(Exception):
    """Classe de base pour les erreurs d'impression."""

    pass


class LabelTemplateNotFoundError(PrinterError):
    """Levée quand le fichier de modèle (.lbx) est introuvable."""

    pass


class LabelAlreadyExistsException(PrinterError):
    """Levée quand un modèle ou un fichier .lbx avec ce nom existe déjà."""

    pass


class LabelFieldNotFoundError(PrinterError):
    """Levée quand un champ demandé n'existe pas dans le modèle."""

    pass


class LabelDataMissingError(PrinterError):
    """Levée quand des données obligatoires pour le modèle sont manquantes."""

    pass


class BpacConnectionError(PrinterError):
    """Levée quand la connexion avec b-PAC (Brother SDK) échoue."""

    pass
