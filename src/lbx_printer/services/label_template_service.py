"""Catalogue of ``.lbx`` templates stored in a directory.

The service is a thin, filesystem-backed library: it lists templates, describes
them by parsing their fields and imports or removes files. It holds no database
state, so it works the same in scripts, desktop applications and services.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..exceptions import LabelAlreadyExistsError, LabelTemplateNotFoundError
from ..lbx.model import TextObject
from ..lbx.parser import LbxParser
from ..models import LabelTemplate

logger = logging.getLogger(__name__)

TEMPLATE_SUFFIX = ".lbx"


class LabelTemplateService:
    """Manage the ``.lbx`` files of a template directory.

    Args:
        template_dir: Directory that stores the templates. It is created on the
            first import.
        parser: Parser used to derive the field names. A default instance is
            created when omitted.

    Example:
        >>> service = LabelTemplateService(Path("templates"))
        >>> template = service.import_file(Path("address.lbx"))
        >>> sorted(template.fields)
        ['address', 'title']
    """

    def __init__(
        self,
        template_dir: str | Path,
        parser: LbxParser | None = None,
    ) -> None:
        self.template_dir = Path(template_dir)
        self._parser = parser or LbxParser()

    def list(self) -> list[LabelTemplate]:
        """Return every readable template of the directory, sorted by name.

        Files that cannot be parsed are logged and skipped so that one damaged
        template does not break the catalogue.
        """
        if not self.template_dir.is_dir():
            return []

        templates: list[LabelTemplate] = []

        for path in sorted(self.template_dir.glob(f"*{TEMPLATE_SUFFIX}")):
            try:
                templates.append(self.describe(path))
            except (OSError, ValueError) as exc:
                logger.warning("Skipping unreadable template %s: %s", path, exc)

        return templates

    def get(self, name: str) -> LabelTemplate:
        """Return the template called ``name``.

        Args:
            name: Template name (file stem) or file name with the ``.lbx``
                suffix.

        Raises:
            LabelTemplateNotFoundError: If the template does not exist or cannot
                be parsed.
        """
        return self.describe(self.resolve_path(name))

    def exists(self, name: str) -> bool:
        """Return whether a template called ``name`` is present."""
        return self._path_for(name).is_file()

    def resolve_path(self, name: str) -> Path:
        """Return the path of the template ``name``.

        Raises:
            LabelTemplateNotFoundError: If the file does not exist.
        """
        path = self._path_for(name)

        if not path.is_file():
            raise LabelTemplateNotFoundError(path)

        return path

    def describe(self, path: str | Path) -> LabelTemplate:
        """Parse ``path`` and return its :class:`LabelTemplate` description.

        Raises:
            LabelTemplateNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid ``.lbx`` archive.
        """
        template_path = Path(path)

        if not template_path.is_file():
            raise LabelTemplateNotFoundError(template_path)

        layout = self._parser.parse(template_path.read_bytes())
        fields = tuple(
            name for name, obj in layout.objects.items() if isinstance(obj, TextObject)
        )

        return LabelTemplate(
            name=template_path.stem,
            template=template_path.name,
            fields=fields,
            description=layout.paper.printer_name,
        )

    def import_file(
        self,
        source: str | Path,
        name: str | None = None,
        description: str = "",
    ) -> LabelTemplate:
        """Copy a template into the directory and return its description.

        The source is parsed before being copied, so invalid archives are
        rejected without touching the directory.

        Args:
            source: Existing ``.lbx`` file.
            name: Optional target name; defaults to the source file stem.
            description: Optional description stored in the result.

        Returns:
            The imported template.

        Raises:
            LabelTemplateNotFoundError: If ``source`` does not exist.
            LabelAlreadyExistsError: If the target name is already used.
            ValueError: If ``source`` is not a valid ``.lbx`` archive.
        """
        source_path = Path(source)

        if not source_path.is_file():
            raise LabelTemplateNotFoundError(source_path)

        target_name = name or source_path.stem

        if self.exists(target_name):
            raise LabelAlreadyExistsError(target_name)

        layout = self._parser.parse(source_path.read_bytes())
        self.template_dir.mkdir(parents=True, exist_ok=True)

        target_path = self._path_for(target_name)
        shutil.copy2(source_path, target_path)

        fields = tuple(
            object_name
            for object_name, obj in layout.objects.items()
            if isinstance(obj, TextObject)
        )

        logger.debug("Imported template %s as %s", source_path, target_path)

        return LabelTemplate(
            name=target_name,
            template=target_path.name,
            fields=fields,
            description=description or layout.paper.printer_name,
        )

    def delete(self, name: str) -> None:
        """Remove the template called ``name``.

        Raises:
            LabelTemplateNotFoundError: If the template does not exist.
        """
        self.resolve_path(name).unlink()

    def _path_for(self, name: str) -> Path:
        clean_name = Path(name)

        if clean_name.suffix.lower() == TEMPLATE_SUFFIX:
            clean_name = clean_name.with_suffix("")

        return self.template_dir / f"{clean_name.name}{TEMPLATE_SUFFIX}"


__all__ = ["TEMPLATE_SUFFIX", "LabelTemplateService"]
