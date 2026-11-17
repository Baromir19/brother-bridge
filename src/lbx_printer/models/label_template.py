"""Immutable description of a label template."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..exceptions import LabelTemplateNotFoundError


@dataclass(frozen=True, slots=True)
class LabelTemplate:
    """A ``.lbx`` template and the fields it exposes.

    Attributes:
        name: Logical template name used by callers.
        template: File name of the template, relative to the template directory.
        fields: Object names that can receive values through ``set_field``.
        description: Optional human-readable description.

    Example:
        >>> template = LabelTemplate("address", "address.lbx", ("title", "address"))
        >>> template.template
        'address.lbx'
    """

    name: str
    template: str
    fields: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))

    def resolve(self, template_dir: str | Path) -> Path:
        """Return the absolute template path inside ``template_dir``.

        Raises:
            LabelTemplateNotFoundError: If the file does not exist.
        """
        path = Path(template_dir) / self.template

        if not path.is_file():
            raise LabelTemplateNotFoundError(path)

        return path


__all__ = ["LabelTemplate"]
