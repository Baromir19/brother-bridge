"""
Implémentation Linux du gestionnaire de documents d'étiquettes Brother.

Orchestre le pipeline complet en mémoire :

    .lbx (bytes)
        │  LbxParser
        ▼
    LabelLayout (RAM)
        │  set_field()
        ▼
    LabelLayout mutée (RAM)
        │  LbxRenderer
        ▼
    PIL.Image (RAM)
        │  PrinterBackend
        ▼
    Brother QL (réseau direct)

Aucune écriture disque n'est effectuée après la lecture initiale du
fichier modèle .lbx.

Résolution automatique du format de bande
------------------------------------------
Le nom de bande brother_ql (ex. ``"62"``, ``"103x164"``) est dérivé
automatiquement des dimensions en points PostScript déclarées dans le
XML .lbx, via :class:`~printers.label_resolver.BrotherQlLabelResolver`.

Aucune table de correspondance hardcodée (format 259 -> "62"…) n'est
nécessaire. Ajouter une nouvelle bande dans brother_ql suffit à ce
que le service la reconnaisse.
"""

from __future__ import annotations

import logging
from pathlib import Path

from brother_ql.labels import FormFactor, LabelsManager

from ..lbx.model import LabelLayout, TextObject
from ..lbx.parser import LbxParser
from ..lbx.renderer import LbxRenderer
from ..printers.backend import PrinterBackend
from ..printers.brother_ql_raster import BrotherQlRasterBackend
from ..printers.label_resolver import BrotherQlLabelResolver
from .label_document import LabelDocument

logger = logging.getLogger(__name__)


class LinuxBrotherDocument(LabelDocument):
    """
    Gestionnaire de documents d'étiquettes pour les systèmes Linux.

    Pipeline entièrement en mémoire : parse -> set_field -> render -> CUPS.

    Les dépendances (renderer, backend d'impression) sont injectables
    pour faciliter les tests sans CUPS ni PIL ::

        doc = LinuxBrotherDocument(
            renderer=FakeRenderer(),
            backend=FakeBackend(),
        )

    Le nom de bande brother_ql est résolu automatiquement à partir de
    la géométrie du papier .lbx via :class:`BrotherQlLabelResolver`.
    Le paramètre ``label`` est conservé uniquement pour surcharge
    explicite ; en l'absence de valeur, la résolution automatique
    s'applique.

    Args:
        renderer: Renderer à utiliser pour convertir le layout en image.
            Si ``None``, un :class:`~lbx.renderer.LbxRenderer` par défaut
            est instancié (police DejaVu, 300 DPI).
        backend:  Backend d'impression. Si ``None``, un
            :class:`~printers.brother_ql_raster.BrotherQlRasterBackend`
            est créé avec les paramètres ``host``, ``model``, ``label``.
        parser:   Parseur .lbx. Si ``None``, une instance de
            :class:`~lbx.parser.LbxParser` par défaut est utilisée.
        label_resolver: Résolveur de bande. Si ``None``, une instance
            de :class:`~printers.label_resolver.BrotherQlLabelResolver`
            est créée.
        host:     Adresse IP de l'imprimante Brother QL (utilisée si
            ``backend`` est ``None``). Par défaut ``"10.10.4.44"``.
        model:    Modèle d'imprimante Brother QL (utilisé si ``backend``
            est ``None``). Par défaut ``"QL-1110NWB"``.
        label:    Identifiant de bande/étiquette brother_ql (utilisé si
            ``backend`` est ``None`` ET qu'aucune résolution n'est
            possible). Obsolète : la résolution automatique par
            géométrie est préférée.
    """

    def __init__(
        self,
        renderer: LbxRenderer | None = None,
        backend: PrinterBackend | None = None,
        parser: LbxParser | None = None,
        label_resolver: BrotherQlLabelResolver | None = None,
        host: str = "10.10.4.44",
        model: str = "QL-1110NWB",
        label: str | None = None,
    ) -> None:
        self._renderer = renderer or LbxRenderer()
        self._label_resolver = label_resolver or BrotherQlLabelResolver()
        self._parser = parser or LbxParser()
        self._backend_override = backend
        self._layout: LabelLayout | None = None
        self._host = host
        self._model = model
        self._override_label = label

    def _initialize(self) -> None:
        """Réinitialise l'état interne à l'entrée du gestionnaire de contexte."""
        self._layout = None
        self._resolved_label: str | None = None

    # close() hérité de LabelDocument - aucune ressource système à libérer.

    def _open(self, path: Path) -> None:
        """
        Lit le fichier .lbx en mémoire et parse le layout.

        Le fichier est lu une seule fois. Après cet appel, ``path`` n'est
        plus accédé - le layout vit entièrement en RAM.

        Le nom de bande brother_ql est résolu automatiquement à partir
        de la géométrie du papier (largeur/hauteur en points + autoLength).

        Args:
            path: Chemin validé vers le fichier modèle .lbx.

        Raises:
            ValueError:         Si ``label.xml`` est absent de l'archive.
            zipfile.BadZipFile: Si le fichier n'est pas une archive ZIP valide.
        """
        raw = path.read_bytes()
        self._layout = self._parser.parse(raw)

        # Résolution automatique du label brother_ql depuis la géométrie
        if self._override_label:
            self._resolved_label = self._override_label
        else:
            self._resolved_label = self._label_resolver.resolve(self._layout.paper)

        logger.debug(
            "Modèle chargé : %s - %d objet(s), bande=%r, "
            "format_id=%d, imprimante XML=%r",
            path.name,
            len(self._layout.objects),
            self._resolved_label,
            self._layout.paper.format_id,
            self._layout.paper.printer_name,
        )

    def _set_field(self, name: str, value: str) -> None:
        """
        Met à jour le texte d'un objet dans le layout en mémoire.

        Args:
            name:  Nom de l'objet (``objectName`` dans le XML).
            value: Nouvelle valeur textuelle.

        Raises:
            RuntimeError:          Si appelé avant :meth:`open`.
            LabelFieldNotFoundError: Si aucun objet ne correspond à ``name``.
            TypeError:             Si l'objet trouvé n'est pas un
                :class:`~lbx.model.TextObject`.
        """
        if self._layout is None:
            raise RuntimeError(
                "set_field() appelé avant open(). "
                "Utilisez LinuxBrotherDocument comme gestionnaire de contexte."
            )

        obj = self._layout.get_object(name)

        if not isinstance(obj, TextObject):
            raise TypeError(
                f"L'objet {name!r} est de type {obj.object_type!r} "
                "et ne peut pas recevoir de valeur textuelle."
            )

        obj.set_text(value)
        logger.debug("Champ mis à jour : %r = %r", name, value)

    def print(self, copies: int = 1, printer: str = "") -> bool:
        """
        Rend l'étiquette et l'envoie à l'imprimante.

        L'imprimante effective est déterminée dans l'ordre :

        1. ``printer`` si non vide.
        2. ``paper.printer_name`` extrait du XML du modèle.
        3. Imprimante par défaut CUPS (chaîne vide transmise à ``lp``).

        Le nom de bande brother_ql est résolu automatiquement à l'ouverture
        du document (voir :meth:`_open`). Chaque appel à ``print`` crée
        un nouveau backend BrotherQLRaster avec le label résolu.

        Args:
            copies:  Nombre d'exemplaires.
            printer: Nom de la file CUPS. Si vide, utilise le nom extrait
                     du XML, ou l'imprimante CUPS par défaut en dernier recours.

        Returns:
            ``True`` si l'envoi a réussi.

        Raises:
            RuntimeError: Si appelé avant :meth:`open`.
        """
        if self._layout is None:
            raise RuntimeError(
                "print() appelé avant open(). "
                "Utilisez LinuxBrotherDocument comme gestionnaire de contexte."
            )

        if self._resolved_label is None:
            raise RuntimeError(
                "Label brother_ql non résolu. _open() n'a probablement pas été appelé."
            )

        effective_printer = printer or self._layout.paper.printer_name

        logger.debug(
            "Rendu de l'étiquette -> imprimante %r, bande=%r, %d exemplaire(s).",
            effective_printer or "(défaut CUPS)",
            self._resolved_label,
            copies,
        )

        image = self._renderer.render(self._layout)

        label_specs = LabelsManager().get_label_by_identifier(self._resolved_label)
        dots_printable = label_specs.dots_printable  # (width_px, height_px)

        image.save("/tmp/label__.png")

        if label_specs.form_factor in (
            FormFactor.DIE_CUT,
            FormFactor.ROUND_DIE_CUT,
        ):
            dx = image.width - dots_printable[0]
            dy = image.height - dots_printable[1]

            left = dx // 2
            right = dx - left

            top = dy // 2
            bottom = dy - top

            image = image.crop(
                (
                    left,
                    top,
                    image.width - right,
                    image.height - bottom,
                )
            )
        else:
            image = image.convert("L")

        logger.debug(
            "Image recadrée à dots_printable : %s px (bande %r).",
            dots_printable,
            self._resolved_label,
        )

        # image.save("/tmp/label.png")

        # Utiliser le backend injecté (tests) ou en créer un nouveau (production)
        backend = self._backend_override or BrotherQlRasterBackend(
            host=self._host,
            model=self._model,
            label=self._resolved_label,
        )

        # return True

        return backend.print(
            image=image,
            printer=effective_printer,
            copies=copies,
        )

    def close(self) -> None:
        pass
