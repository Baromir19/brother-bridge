# API reference

Everything below is importable from the package root. Names prefixed with `_`
are internal.

## Models

### `LabelTemplate`

```python
@dataclass(frozen=True)
class LabelTemplate:
    name: str
    template: str
    fields: tuple[str, ...] = ()
    description: str = ""

    def resolve(self, template_dir: str | Path) -> Path: ...
```

Immutable description of a template. `template` is the file name inside the
template directory. `resolve()` raises `LabelTemplateNotFoundError` when the file
is absent.

### `LabelData`

```python
@dataclass
class LabelData:
    values: dict[str, str]

    def get(self, key: str, default: str | None = None) -> str | None: ...
    def as_dict(self) -> dict[str, str]: ...
    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> LabelData: ...
```

Field values keyed by template object name. Supports `data[key]`, `key in data`,
iteration and `len()`. Values are stringified on construction.

### `PrintRequest`

```python
@dataclass
class PrintRequest:
    label: LabelTemplate
    data: LabelData
    copies: int = 1
    printer: str = ""

    def missing_fields(self) -> tuple[str, ...]: ...
```

Raises `ConfigurationError` when `copies < 1`.

### `PrintMode`

`IntEnum` of b-PAC print options. `PrintMode.NORMAL == 0` maps to
`b_Print_Default`.

## Parsing and rendering

### `LbxParser`

```python
class LbxParser:
    def parse(self, data: bytes | BinaryIO) -> LabelLayout: ...
    def parse_file(self, path: str | Path) -> LabelLayout: ...
```

Stateless and thread-safe. Raises `zipfile.BadZipFile` for non-ZIP input and
`ValueError` when required XML elements are missing.

### `LbxRenderer`

```python
class LbxRenderer:
    def __init__(self, font_resolver: FontResolver | None = None, dpi: int = 300): ...
    def render(self, layout: LabelLayout) -> Image.Image: ...
```

Returns a mode `"1"` image whose width equals the tape width in dots at `dpi`.
Continuous tape grows with the content; landscape designs are rotated so the
image feeds correctly on the printer.

### `FontResolver`

```python
class FontResolver:
    def __init__(
        self,
        substitutions: Mapping[str, str | Sequence[str]] | None = None,
        extra_dirs: Sequence[Path] | None = None,
    ): ...
    def resolve(
        self, name: str, bold: bool = False, italic: bool = False, size_px: int = 12
    ) -> ImageFont.FreeTypeFont: ...
    def available_families(self) -> tuple[str, ...]: ...
```

Maps P-touch font names onto installed fonts. Resolution order: exact family,
substitution table, partial match, bundled font, Pillow default. Results are
cached and the resolver is thread-safe.

### Layout model

`LabelLayout(paper: PaperSpec, objects: dict[str, LabelObject])` with
`get_object(name)` and the `text_objects` view.

Object types: `TextObject`, `BarcodeObject`, `ImageObject` (the latter two are
parsed but not rendered). `TextObject.set_text(value)` replaces the content and
collapses formatting to `default_font`.

`PaperSpec` exposes `width_pt`, `height_pt`, `auto_length`, margins,
`orientation`, `printer_name`, `format_id`, plus `exact_width_mm`,
`exact_height_mm`, `width_mm` and `height_mm`.

## Documents

### `document_factory`

```python
def document_factory(
    config: PrinterConfig | None = None,
    *,
    renderer: LbxRenderer | None = None,
    backend: PrinterBackend | None = None,
    platform_name: str | None = None,
) -> LabelDocument: ...
```

Returns `BpacDocument` on Windows and `LinuxBrotherDocument` elsewhere.
`config` defaults to `PrinterConfig.from_env()`.

### `LabelDocument`

```python
class LabelDocument(ABC):
    def __enter__(self) -> LabelDocument: ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def open(self, path: str | Path) -> None: ...
    def set_field(self, name: str, value: Any) -> None: ...
    def set_fields(self, values: Mapping[str, Any]) -> None: ...
    def print(self, copies: int = 1, printer: str = "") -> bool: ...
```

Subclasses implement `_open`, `_set_field`, `print` and optionally `_initialize`
and `close`.

## Backends

Every backend implements:

```python
class PrinterBackend(ABC):
    def print(self, image: Image.Image, printer: str, copies: int = 1) -> bool: ...
```

| Class | Transport | Notes |
| --- | --- | --- |
| `BrotherQlRasterBackend(host, model, label, port=9100, cut=True, threshold=70.0, dither=False)` | Raw Brother raster over TCP | `printer` argument ignored |
| `CupsPngBackend(lp_path="lp", timeout=30)` | PNG piped to `lp` | `printer` is the queue name |
| `FileBackend(output_dir, prefix="label", image_format="PNG")` | Image files | For previews and tests |

### `BrotherQlLabelResolver`

```python
class BrotherQlLabelResolver:
    def __init__(self) -> None: ...
    def resolve(self, paper: PaperSpec) -> str: ...
```

Returns the closest `brother_ql` identifier; raises `UnsupportedLabelError` when
the distance exceeds `MAX_DISTANCE_MM` (2 mm). Requires the `brother` extra.

## Services

### `LabelPrinterService`

```python
class LabelPrinterService:
    def __init__(
        self,
        template_dir: str | Path,
        document_factory: Callable[[], LabelDocument] | None = None,
    ): ...
    def print_label(self, request: PrintRequest) -> bool: ...
```

Validates the template path and required fields, then opens a document, applies
values and prints.

### `LabelTemplateService`

```python
class LabelTemplateService:
    def __init__(self, template_dir: str | Path, parser: LbxParser | None = None): ...
    def list(self) -> list[LabelTemplate]: ...
    def get(self, name: str) -> LabelTemplate: ...
    def exists(self, name: str) -> bool: ...
    def resolve_path(self, name: str) -> Path: ...
    def describe(self, path: str | Path) -> LabelTemplate: ...
    def import_file(self, source, name=None, description="") -> LabelTemplate: ...
    def delete(self, name: str) -> None: ...
```

Filesystem catalogue of `.lbx` files. `import_file` validates the archive before
copying and raises `LabelAlreadyExistsError` on name collisions.

## Configuration

```python
@dataclass(frozen=True)
class PrinterConfig:
    host: str = "10.10.4.44"
    model: str = "QL-1110NWB"
    label: str | None = None
    port: int = 9100
    cut: bool = True
    threshold: float = 70.0
    dither: bool = False
    dpi: int = 300
    template_dir: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PrinterConfig: ...
    def with_overrides(self, **changes: Any) -> PrinterConfig: ...
    def to_dict(self) -> dict[str, Any]: ...
```

See the README for the environment variable names.

## Utilities

### `LbxUtils`

```python
class LbxUtils:
    @staticmethod
    def extract_fields(path, *, text_only: bool = False) -> list[str]: ...
    @staticmethod
    def read_paper(path) -> PaperSpec: ...
```

### `lbx_printer.logging`

`get_logger(name)` and `configure_logging(level, stream, fmt)`.

### `lbx_printer.i18n`

`translate(key, **values)`, `set_locale(code)`, `get_locale()`,
`available_locales()`, `DEFAULT_LOCALE`, `LOCALE_ENVIRONMENT_VARIABLE`.

## Exceptions

| Exception | Meaning |
| --- | --- |
| `PrinterError` | Base class |
| `ConfigurationError` | Invalid or missing configuration value |
| `MissingDependencyError` | Optional dependency not installed |
| `LabelTemplateNotFoundError` | Template file missing or unreadable by the platform |
| `LabelAlreadyExistsError` | Duplicate template name |
| `LabelFieldNotFoundError` | Unknown template field |
| `LabelDataMissingError` | Required field has no value |
| `PrinterStateError` | Document used before `open()` |
| `BpacConnectionError` | b-PAC COM SDK unavailable or failing |
| `UnsupportedLabelError` | No `brother_ql` tape matches the geometry |
