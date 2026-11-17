"""Platform-neutral entry point for label documents.

:func:`document_factory` selects an implementation for the current platform:

* Windows: :class:`~brother_bridge.managers.bpac_document.BpacDocument`, which
  drives the native Brother b-PAC COM SDK.
* Linux and macOS:
  :class:`~brother_bridge.managers.linux_brother_document.LinuxBrotherDocument`,
  which renders the template in memory and sends raster data directly.

Imports of the concrete classes are deferred to the factory so that no COM
dependency is needed on POSIX systems and no raster dependency on Windows.
"""

from __future__ import annotations

import platform

from ..config import PrinterConfig
from ..lbx.renderer import LbxRenderer
from ..printers.backend import PrinterBackend
from .label_document import LabelDocument


def document_factory(
    config: PrinterConfig | None = None,
    *,
    renderer: LbxRenderer | None = None,
    backend: PrinterBackend | None = None,
    platform_name: str | None = None,
) -> LabelDocument:
    """Create a document manager for a platform.

    Args:
        config: Settings for the default backend. When omitted,
            :meth:`PrinterConfig.from_env` is used.
        renderer: Optional renderer override for the POSIX implementation.
        backend: Optional backend override for the POSIX implementation.
        platform_name: Override the detected platform (``"Windows"``,
            ``"Linux"``, ...). Intended for tests.

    Returns:
        A fresh :class:`LabelDocument`. Use it as a context manager so that
        platform resources are acquired and released correctly.
    """
    settings = config or PrinterConfig.from_env()
    system = platform_name or platform.system()

    if system == "Windows":
        from .bpac_document import BpacDocument

        return BpacDocument()

    from .linux_brother_document import LinuxBrotherDocument

    return LinuxBrotherDocument(
        renderer=renderer,
        backend=backend,
        host=settings.host,
        model=settings.model,
        label=settings.label,
        dpi=settings.dpi,
    )


__all__ = ["LabelDocument", "document_factory"]
