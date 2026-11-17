# lbx-printer

Parse, fill and print Brother P-touch (`.lbx`) label templates from Python.

The package reads the template archive that P-touch Editor produces, exposes its
text fields, renders the design to a monochrome bitmap and sends it to the
printer. Windows uses the native Brother **b-PAC** COM SDK; Linux and macOS use
the in-memory renderer with either direct Brother raster output or CUPS. The
same code path is used for previews, tests and production printing.

```python
from pathlib import Path

from lbx_printer import LabelData, LabelPrinterService, LabelTemplate, PrintRequest

request = PrintRequest(
    label=LabelTemplate("address", "address.lbx", ("title", "address")),
    data=LabelData({"title": "Ada Lovelace", "address": "London"}),
)

LabelPrinterService(Path("templates")).print_label(request)
```

## Features

- **Template parsing** - reads `label.xml` from the `.lbx` ZIP container and
  builds an in-memory layout of paper, text, barcode and image objects.
- **Rendering without hardware** - converts a layout to a 300 DPI monochrome
  `PIL.Image`, honouring fonts, alignment, word wrap, auto line feed, shrink-to-fit
  and continuous or die-cut tape geometry.
- **Automatic tape resolution** - the `brother_ql` tape identifier is derived
  from the paper geometry, so no format table has to be maintained.
- **Pluggable transport** - direct Brother raster over TCP, CUPS queues or plain
  image files. The backend is an abstract interface and can be replaced.
- **Platform isolation** - the b-PAC (COM) and raster implementations are loaded
  lazily, so the package imports on any OS and degrades with clear errors.
- **Dependency injection** - documents, renderers, parsers, tape resolvers and
  backends are all injectable; nothing is bound to global state.
- **Typed and tested** - `py.typed`, strict MyPy on the package, unit and
  integration tests, CI for Linux and Windows.

## Requirements

| Platform | Printing requires |
| --- | --- |
| Windows | Brother b-PAC SDK (COM) and `pywin32` |
| Linux / macOS | `brother_ql` and a reachable printer (direct raster), or CUPS with a working queue |
| Any | Pillow is the only mandatory runtime dependency |

Rendering, parsing and previews work on every platform with just Pillow;
`fonttools` (installed by default) is used for better font family detection.

## Installation

```bash
pip install lbx-printer            # core: parse and render
pip install "lbx-printer[brother]" # Linux/macOS raster printing
pip install "lbx-printer[windows]" # Windows b-PAC printing (pywin32)
pip install "lbx-printer[all]"     # everything
```

The `brother` extra installs the `brother_ql` release available on PyPI. Models
and labels introduced after that release (for example the QL-1110NWB) require the
upstream build, so install it before the package:

```bash
pip install "brother-ql @ git+https://github.com/pklaus/brother_ql.git"
pip install lbx-printer
```

Windows printing does not need `brother_ql` at all.

Development install:

```bash
git clone https://github.com/Baromir19/brother
cd brother
python -m venv .venv
.venv/Scripts/activate    # Windows
pip install -e ".[all,dev]"
```

## Quick start

### Print a label

```python
from pathlib import Path

from lbx_printer import LabelData, LabelPrinterService, LabelTemplate, PrintRequest

service = LabelPrinterService(Path("templates"))
request = PrintRequest(
    label=LabelTemplate(
        name="address",
        template="address.lbx",
        fields=("title", "address"),
    ),
    data=LabelData(
        {
            "title": "Ada Lovelace",
            "address": "12 rue de la Paix\n75002 Paris",
        }
    ),
    copies=2,
    printer="",  # empty: platform default or the printer stored in the template
)
service.print_label(request)
```

### Render a preview

```python
from pathlib import Path

from lbx_printer import FileBackend, LbxParser, LbxRenderer

layout = LbxParser().parse_file(Path("templates/address.lbx"))
layout.text_objects["title"].set_text("Ada Lovelace")

image = LbxRenderer().render(layout)
image.save("preview.png")
FileBackend(Path("output")).print(image, printer="", copies=1)
```

### Drive a platform document directly

```python
from lbx_printer import PrinterConfig, document_factory

config = PrinterConfig(host="192.168.1.50", model="QL-1110NWB")
with document_factory(config) as document:
    document.open("templates/address.lbx")
    document.set_fields({"title": "Ada Lovelace", "address": "London"})
    document.print(copies=1)
```

## Configuration

`PrinterConfig` is an immutable dataclass; it can be built explicitly or from
the environment. Malformed values raise `ConfigurationError` instead of failing
later at print time.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LBX_PRINTER_HOST` | `10.10.4.44` | Printer address for the raster backend |
| `LBX_PRINTER_MODEL` | `QL-1110NWB` | Model name understood by `brother_ql` |
| `LBX_PRINTER_LABEL` | auto | Explicit tape identifier; empty means auto-detect |
| `LBX_PRINTER_PORT` | `9100` | Raw TCP port |
| `LBX_PRINTER_CUT` | `true` | Cut after each copy |
| `LBX_PRINTER_THRESHOLD` | `70` | Black/white threshold in percent |
| `LBX_PRINTER_DITHER` | `false` | Dither instead of thresholding |
| `LBX_PRINTER_DPI` | `300` | Rendering resolution |
| `LBX_PRINTER_TEMPLATE_DIR` | unset | Default template directory |
| `LBX_PRINTER_LOCALE` | `en` | Locale of exception messages (`en`, `fr`) |

## Public API

The stable surface is exported from the package root and listed in
`lbx_printer.__all__`:

- Models: `LabelTemplate`, `LabelData`, `PrintRequest`, `PrintMode`
- Pipeline: `LbxParser`, `LbxRenderer`, `FontResolver`, `LabelLayout`,
  `TextObject`, `PaperSpec`
- Documents: `document_factory`, `LabelDocument`
- Backends: `PrinterBackend`, `BrotherQlRasterBackend`, `CupsPngBackend`,
  `FileBackend`, `BrotherQlLabelResolver`
- Services: `LabelPrinterService`, `LabelTemplateService`
- Support: `PrinterConfig`, `LbxUtils`, the exception hierarchy

See [`docs/api.md`](docs/api.md) for signatures and [`docs/user-guide.md`](docs/user-guide.md)
for task-oriented guidance.

## Platform behaviour

| | Windows | Linux / macOS |
| --- | --- | --- |
| Document class | `BpacDocument` (COM, b-PAC) | `LinuxBrotherDocument` (in memory) |
| Template handling | Native b-PAC template | Parsed and rendered by this package |
| Transport | b-PAC print job | `BrotherQlRasterBackend` (TCP) or `CupsPngBackend` (`lp`) |
| Tape resolution | Provided by b-PAC | `BrotherQlLabelResolver` from paper geometry |

`document_factory()` picks the implementation for the current platform. Pass
`platform_name="Linux"` or `platform_name="Windows"` to force one, for example in
tests.

## Extending

- **New transport**: implement `PrinterBackend.print(image, printer, copies)` and
  pass an instance to `LinuxBrotherDocument(backend=...)` or
  `LabelPrinterService(..., document_factory=...)`.
- **New document manager**: subclass `LabelDocument` and implement `_open`,
  `_set_field` and `print`.
- **Custom fonts**: `FontResolver(extra_dirs=[...], substitutions={...})`.
- **Custom geometry**: a `tape_spec_provider` callable can replace the
  `brother_ql` catalogue lookup.

## Errors, logging and locale

All package exceptions derive from `PrinterError`. Messages are translated
(English and French ship in the box), while structured attributes such as
`LabelFieldNotFoundError.name` remain available for programmatic handling.

The package never configures the root logger. Add a handler when needed:

```python
from lbx_printer.logging import configure_logging

configure_logging("DEBUG")
```

Set `LBX_PRINTER_LOCALE=fr` (or call `lbx_printer.i18n.set_locale("fr")`) to
localise exception messages.

## Thread safety

`LbxParser`, `LbxRenderer`, `FontResolver`, `BrotherQlLabelResolver` and the
print backends are safe to share between threads. `LabelDocument` instances are
not: one document belongs to one thread and one job, and b-PAC in particular is
COM apartment-bound. Do not share a document between threads.

## Documentation

| Document | Content |
| --- | --- |
| [`docs/user-guide.md`](docs/user-guide.md) | Installation, templates, printing, troubleshooting |
| [`docs/architecture.md`](docs/architecture.md) | Layers, data flow, design decisions, extension points |
| [`docs/developer-guide.md`](docs/developer-guide.md) | Development setup, tests, typing, build, release |
| [`docs/api.md`](docs/api.md) | Public API reference |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |

## Versioning

The package follows [Semantic Versioning](https://semver.org/). The public API is
the set of names exported from `lbx_printer`; everything else (module-internal
helpers prefixed with `_`) may change in a minor release. Deprecations are
introduced with a warning and removed only in the next major version.

## License

GNU General Public License v3.0 or later. See [`LICENSE`](LICENSE).
`brother_ql` (installed as an optional dependency) is distributed under GPLv3 as
well; Pillow, fonttools and pywin32 keep their own licenses. No third-party code
is vendored into this repository.
