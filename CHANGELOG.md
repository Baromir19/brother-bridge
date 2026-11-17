# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-17

### Added

- Standalone, pip-installable distribution `brother-bridge` with a `src/` layout,
  `py.typed` marker and a single public API exported from `brother_bridge`.
- In-memory `.lbx` pipeline: `LbxParser`, `LbxRenderer`, `FontResolver` and the
  layout model (`LabelLayout`, `PaperSpec`, `TextObject`, `Run`, `FontSpec`).
- Cross-platform font discovery (Linux, macOS, Windows) with platform-aware
  substitutions, deterministic regular-face selection, thread-safe cache and a
  scalable Pillow fallback.
- Tape resolution from paper geometry (`BrotherQlLabelResolver`) with a 2 mm
  tolerance; continuous and die-cut tape are matched separately.
- Pluggable transports: `BrotherQlRasterBackend` (raw raster over TCP),
  `CupsPngBackend` (`lp` with PNG on stdin) and `FileBackend` (previews).
- Platform documents: `BpacDocument` for Windows COM and
  `LinuxBrotherDocument` for in-memory rendering, selected by
  `document_factory()`.
- Dependency injection for parsers, renderers, tape resolvers, backends and
  document factories.
- `PrinterConfig` with environment support and eager validation; per-job
  configuration instead of global state.
- Filesystem template catalogue (`LabelTemplateService`): list, describe,
  import and delete `.lbx` templates.
- Localised exception messages (English and French) through `brother_bridge.i18n`.
- Optional logging helpers that never reconfigure the root logger.
- Unit, integration and opt-in hardware test suites; strict MyPy configuration;
  Ruff configuration; CI workflow for Linux and Windows.

### Changed

- Rendering and printing are fully decoupled: the renderer returns a Pillow
  image and backends only transport it.
- Debug dumps to `/tmp` were removed; use `FileBackend` or debug logging instead.

### Fixed

- Die-cut tape resolution no longer degenerates to a zero distance, which
  previously selected the first catalogue entry instead of the closest label.
- Font family matching is case- and separator-insensitive and prefers the
  regular face of a family over arbitrary variants.
- The raster backend no longer writes an unconditional debug file.

[1.0.0]: https://github.com/Baromir19/brother/releases/tag/v1.0.0
