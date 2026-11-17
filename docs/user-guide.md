# User guide

## 1. Prepare a template

Design the label in Brother P-touch Editor, save it as `.lbx` and copy the file
into a template directory, for example `templates/address.lbx`.

Two properties of the template matter:

- **Object names** - every text object that should receive a value needs a name.
  In P-touch Editor this is the object's name in the property panel; it is stored
  as `objectName` in the archive.
- **Paper settings** - tape width, continuous or die-cut paper and orientation
  come from the template. The package uses them to choose the printable area and
  the `brother_ql` tape identifier.

List the fields of a template without printing anything:

```python
from pathlib import Path

from brother_bridge import LabelTemplateService

service = LabelTemplateService(Path("templates"))
for template in service.list():
    print(template.name, template.fields)
```

## 2. Install for the target platform

```bash
pip install brother-bridge                  # parsing and rendering
pip install "brother-bridge[brother]"       # Linux/macOS raster printing
pip install "brother-bridge[windows]"       # Windows b-PAC printing
```

The `brother` extra installs the `brother_ql` version published on PyPI. If the
printer model or tape was added after that release (the QL-1110NWB is one of
them), install the upstream build first; otherwise `brother_ql` raises an
unknown-model error at print time or the tape cannot be resolved:

```bash
pip install "brother-ql @ git+https://github.com/pklaus/brother_ql.git"
pip install brother-bridge
```

**Windows**: install the Brother b-PAC SDK (it ships with the printer software
and registers the `bpac.Document` COM class).

**Linux**: make sure the printer is reachable over the network and that the
model name matches a `brother_ql` model, for example `QL-1110NWB`. Port 9100
must be open.

**CUPS**: if a queue already exists, use `CupsPngBackend` instead of the raster
backend. The queue must accept PNG input, which the Brother QL drivers do.

## 3. Configure

Either pass a `PrinterConfig` explicitly or set environment variables:

```bash
export BROTHER_BRIDGE_HOST=192.168.1.50
export BROTHER_BRIDGE_MODEL=QL-1110NWB
export BROTHER_BRIDGE_DPI=300
```

```python
from brother_bridge import PrinterConfig

config = PrinterConfig.from_env()
tuned = config.with_overrides(host="192.168.1.60", cut=False)
```

Invalid values raise `ConfigurationError` immediately, for example a port outside
1..65535 or a threshold outside 0..100.

## 4. Print

```python
from pathlib import Path

from brother_bridge import LabelData, LabelPrinterService, LabelTemplate, PrintRequest

service = LabelPrinterService(Path("templates"))
request = PrintRequest(
    label=LabelTemplate("address", "address.lbx", ("title", "address")),
    data=LabelData({"title": "Ada Lovelace", "address": "London"}),
    copies=1,
)
service.print_label(request)
```

`PrintRequest.printer` selects the target:

- Windows: the printer name passed to b-PAC; empty means the default printer.
- Linux with CUPS: the queue name; empty means the default queue.
- Linux with the raster backend: ignored; the address comes from
  `PrinterConfig.host`.

When `printer` is empty on Linux, the printer name stored in the template is
used, and if that is empty too, the platform default applies.

## 5. Preview and troubleshoot without hardware

```python
from pathlib import Path

from brother_bridge import FileBackend, LbxParser, LbxRenderer

layout = LbxParser().parse_file(Path("templates/address.lbx"))
layout.text_objects["title"].set_text("Preview")
image = LbxRenderer().render(layout)
FileBackend(Path("output")).print(image, printer="", copies=1)
```

The PNG in `output/` has exactly the pixel size that would be sent to the
printer, which makes layout problems obvious before any tape is consumed.

## Common problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| `MissingDependencyError: brother_ql` | Raster extra not installed | `pip install "brother-bridge[brother]"` |
| `BpacConnectionError` on Windows | b-PAC SDK missing or not registered | Install the Brother printer software and `pywin32` |
| `UnsupportedLabelError` | Template geometry has no close match in `brother_ql` | Check the tape settings in the template, or pass an explicit `label=` |
| `LabelFieldNotFoundError` | The field name does not exist in the template | Use `LabelTemplateService(...).get(name).fields` |
| `LabelDataMissingError` | A declared field has no value | Provide every name from `LabelTemplate.fields` |
| Text is tiny | Shrink-to-fit reduced the font because the box is small | Enlarge the object in P-touch Editor |
| Text is clipped | Object has `autoLF=false` and contains no newlines | Enable auto line feed or add newlines to the value |
| `lp` not found | CUPS client tools missing | Install `cups-client` (Linux) or use the raster backend |
| Nothing printed but no error | Wrong host or port | Verify `BROTHER_BRIDGE_HOST`, `BROTHER_BRIDGE_PORT` and network access |

## Logging

Logging is silent by default. Enable it for diagnostics:

```python
from brother_bridge.logging import configure_logging

configure_logging("DEBUG")
```

The most useful debug records are the parsed layout, the resolved tape
identifier, the canvas size and the backend target.

## Localisation

Exception messages are available in English and French. Select the locale with
`BROTHER_BRIDGE_LOCALE=fr` or programmatically:

```python
from brother_bridge.i18n import set_locale

set_locale("fr")
```

Attribute access (`error.name`, `error.fields`, `error.target`) does not depend
on the locale, so application logic can stay locale-independent.
