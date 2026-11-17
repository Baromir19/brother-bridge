"""Print modes understood by the Brother b-PAC SDK."""

from enum import IntEnum


class PrintMode(IntEnum):
    """b-PAC print option flags.

    ``NORMAL`` maps to ``b_Print_Default``: print every page with the settings
    stored in the template.
    """

    NORMAL = 0


__all__ = ["PrintMode"]
