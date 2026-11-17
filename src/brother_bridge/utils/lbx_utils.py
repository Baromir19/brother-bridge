"""Convenience helpers for inspecting ``.lbx`` files without opening them."""

from __future__ import annotations

from pathlib import Path

from ..lbx.model import PaperSpec
from ..lbx.parser import LbxParser


class LbxUtils:
    """Static helpers around :class:`~brother_bridge.lbx.parser.LbxParser`."""

    @staticmethod
    def extract_fields(path: str | Path, *, text_only: bool = False) -> list[str]:
        """Return the object names declared by a template.

        Args:
            path: ``.lbx`` file to read.
            text_only: When true, only objects that accept text values are
                returned.

        Returns:
            Object names in template order, without duplicates.
        """
        layout = LbxParser().parse(Path(path).read_bytes())

        if text_only:
            return list(layout.text_objects)

        return list(layout.objects)

    @staticmethod
    def read_paper(path: str | Path) -> PaperSpec:
        """Return the paper description of a template."""
        return LbxParser().parse(Path(path).read_bytes()).paper


__all__ = ["LbxUtils"]
