# Developer guide

## Repository layout

```text
brother-bridge/
├── src/brother_bridge/          # the package (src layout)
│   ├── __init__.py           # public API and __version__
│   ├── config.py             # PrinterConfig
│   ├── exceptions.py         # exception hierarchy
│   ├── i18n.py               # message catalogues and translate()
│   ├── logging.py            # logger helpers
│   ├── lbx/                  # parsing, layout model, rendering, fonts
│   ├── managers/             # platform documents and document_factory
│   ├── models/               # value objects
│   ├── printers/             # transport backends and tape resolver
│   ├── resources/fonts/      # optional bundled fonts
│   ├── services/             # application-level helpers
│   └── utils/                # LbxUtils
├── tests/
│   ├── fixtures/printer/     # real .lbx fixtures
│   ├── unit/                 # fast, isolated tests
│   ├── integration/          # multi-component tests
│   └── live/                 # hardware tests (opt-in)
├── docs/
├── pyproject.toml
└── CHANGELOG.md
```

## Environment

Python 3.10 or newer is required. The project has no build-time code generation.

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
source .venv/bin/activate       # Linux/macOS
python -m pip install -e ".[all,dev]"
# The PyPI release of brother_ql lacks recent printers and labels used by the
# tests; replace it with the upstream build.
python -m pip install --force-reinstall --no-deps \
    "brother-ql @ git+https://github.com/pklaus/brother_ql.git"
```

Alternatively, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras
```

## Commands

| Task | Command |
| --- | --- |
| Run unit and integration tests | `pytest` |
| Run only unit tests | `pytest -m unit` |
| Run only integration tests | `pytest -m integration` |
| Run with coverage | `pytest --cov --cov-report=term-missing` |
| Run hardware tests | `BROTHER_BRIDGE_HOST=... pytest -m live` |
| Lint | `ruff check src tests` |
| Check formatting | `ruff format --check src tests` |
| Apply formatting | `ruff format src tests` |
| Type check | `mypy` |
| Build distributions | `python -m build` |
| Verify metadata | `twine check dist/*` |

CI runs the same commands on Linux and Windows.

## Testing conventions

- Mark every test module with `pytestmark = pytest.mark.unit`,
  `pytest.mark.integration` or `pytest.mark.live`. The default run excludes
  `live`.
- Unit tests must not touch the network, CUPS, COM or real printers.
- Tests that need a template use the `address_lbx` fixture, or build a synthetic
  archive with `lbx_factory`, `text_object`, `barcode_object` and `image_object`
  from `tests/conftest.py`.
- Backends are replaced with recording fakes:
  `LinuxBrotherDocument(backend=Fake(), tape_spec_provider=...)`.
- Font-dependent tests skip when the machine has no TrueType fonts.
- A regression test guards the die-cut tape resolution; keep it green.

## Code conventions

- Type annotations are mandatory in `src/`; MyPy runs in strict mode on the
  package. Tests relax annotation rules only for fixtures and helpers.
- Public names are documented and exported through `__all__`. Anything else
  stays private (`_name`).
- No global mutable state. Configuration is passed as `PrinterConfig`;
  dependencies are injected through constructor arguments.
- No hidden I/O: the library never writes files unless `FileBackend` is used
  explicitly, and never configures logging on import.
- Log records are English and developer-oriented; user-facing messages belong to
  `i18n`.
- Docstrings describe behaviour, arguments, returns, raised exceptions and
  thread-safety implications. Comments are reserved for non-obvious invariants.

## Adding a backend

```python
from PIL import Image

from brother_bridge import PrinterBackend


class SpoolerBackend(PrinterBackend):
    def print(self, image: Image.Image, printer: str, copies: int = 1) -> bool:
        ...
        return True
```

Use it by injecting it:

```python
from brother_bridge.managers import document_factory

document_factory(backend=SpoolerBackend(), platform_name="Linux")
```

Add unit tests with a fake `tape_spec_provider` and document any platform
requirement in the class docstring.

## Adding a locale

1. Add a catalogue to `_MESSAGES` in `src/brother_bridge/i18n.py`.
2. Keep the same keys as the English catalogue.
3. Add a test that a representative message is translated.

## Versioning and release

1. The version lives in `src/brother_bridge/__init__.py` and is read by Hatch, so
   there is a single source of truth.
2. Update `CHANGELOG.md` under the version being released.
3. Run the local gate: `ruff check src tests`, `ruff format --check src tests`,
   `mypy`, `pytest`.
4. Build and verify: `python -m build && twine check dist/*`.
5. Commit, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.

The tag starts two GitHub Actions workflows:

- `ci.yml` - lint, type check, tests on Linux and Windows, build and wheel smoke
  test.
- `release.yml` - rebuilds the distributions, checks that the tag matches
  `__version__`, uploads the artifact and publishes to PyPI through
  [trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no API
  token in secrets).

One-time PyPI configuration: on the project's *Publishing* page add a trusted
publisher with owner `Baromir19`, repository `brother`, workflow `release.yml`
and environment `pypi`. The same environment name is referenced in the workflow.

Metadata rule: PyPI rejects distributions whose `Requires-Dist` contains a
direct URL reference. Keep `pyproject.toml` free of `pkg @ git+...` entries;
install such builds manually and document them in the user guide instead.

Semantic versioning applies to the public API exported from `brother_bridge`:

- **major** - removed or changed public behaviour.
- **minor** - new public functionality, deprecations.
- **patch** - fixes that keep the API intact.

## Third-party compliance

- Pillow, fonttools and pywin32 are used under their own licenses, as declared
  in `pyproject.toml`.
- `brother_ql` is optional and installed from its upstream repository because
  the PyPI release does not include recent printers.
- No third-party source code is vendored. Fonts are not redistributed; the
  optional `src/brother_bridge/resources/fonts` directory exists for deployments
  that provide their own font files.
