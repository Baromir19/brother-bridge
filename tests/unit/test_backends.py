"""Unit tests for the print backends."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest
from PIL import Image

from lbx_printer.exceptions import MissingDependencyError
from lbx_printer.printers import (
    BrotherQlRasterBackend,
    CupsPngBackend,
    FileBackend,
    PrinterBackend,
    brother_ql_raster,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def image() -> Image.Image:
    return Image.new("1", (120, 60), color=1)


def test_file_backend_writes_one_file_per_copy(
    tmp_path: Path, image: Image.Image
) -> None:
    backend = FileBackend(tmp_path / "labels", prefix="test")

    assert backend.print(image, printer="", copies=3) is True

    written = sorted((tmp_path / "labels").glob("test_*.png"))
    assert len(written) == 3
    assert all(path.stat().st_size > 0 for path in written)
    assert Image.open(written[0]).size == (120, 60)


def test_file_backend_supports_bmp(tmp_path: Path, image: Image.Image) -> None:
    backend = FileBackend(tmp_path, prefix="bmp", image_format="BMP")
    backend.print(image, printer="", copies=1)

    assert list(tmp_path.glob("bmp_*.bmp"))


def test_file_backend_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported image format"):
        FileBackend(tmp_path, image_format="TIFF")


def test_cups_backend_builds_the_expected_command() -> None:
    backend = CupsPngBackend()

    assert backend.build_command("", 1) == ["lp", "-"]
    assert backend.build_command("Brother_QL", 2) == [
        "lp",
        "-d",
        "Brother_QL",
        "-n",
        "2",
        "-",
    ]


def test_cups_backend_pipes_png_into_lp(
    monkeypatch: pytest.MonkeyPatch, image: Image.Image
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, input, capture_output, timeout, check):
        captured.update(
            command=command,
            input=input,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
        )

        return subprocess.CompletedProcess(command, 0, stdout=b"request id", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert CupsPngBackend().print(image, printer="queue", copies=2) is True
    assert captured["command"] == ["lp", "-d", "queue", "-n", "2", "-"]
    assert cast(bytes, captured["input"]).startswith(b"\x89PNG")
    assert captured["check"] is True


def test_cups_backend_reports_a_missing_lp(
    monkeypatch: pytest.MonkeyPatch, image: Image.Image
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("lp")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MissingDependencyError, match="lp"):
        CupsPngBackend().print(image, printer="", copies=1)


def test_cups_backend_propagates_lp_failures(
    monkeypatch: pytest.MonkeyPatch, image: Image.Image
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(1, "lp", output=b"", stderr=b"bad queue")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        CupsPngBackend().print(image, printer="missing", copies=1)


def test_raster_backend_sends_the_converted_image(
    monkeypatch: pytest.MonkeyPatch, image: Image.Image
) -> None:
    calls: dict[str, object] = {}

    class FakeRaster:
        exception_on_warning = False

        def __init__(self, model: str) -> None:
            calls["model"] = model

    def fake_convert(**kwargs: object) -> bytes:
        calls["convert"] = kwargs

        return b"raster-bytes"

    def fake_send(**kwargs: object) -> None:
        calls["send"] = kwargs

    monkeypatch.setattr(
        brother_ql_raster,
        "_import_brother_ql",
        lambda: (fake_send, fake_convert, FakeRaster),
    )

    backend = BrotherQlRasterBackend(host="10.0.0.9", model="QL-1110NWB", label="62")

    assert backend.print(image, printer="ignored", copies=2) is True
    assert calls["convert"]["label"] == "62"  # type: ignore[index]
    assert len(calls["convert"]["images"]) == 2  # type: ignore[index]
    assert calls["send"]["printer_identifier"] == "tcp://10.0.0.9:9100"  # type: ignore[index]
    assert calls["send"]["instructions"] == b"raster-bytes"  # type: ignore[index]


def test_raster_backend_is_a_printer_backend() -> None:
    backend = BrotherQlRasterBackend(host="127.0.0.1", model="QL-800", label="29")

    assert isinstance(backend, PrinterBackend)
