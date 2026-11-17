"""Unit tests for the template catalogue."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from lbx_printer.exceptions import (
    LabelAlreadyExistsError,
    LabelTemplateNotFoundError,
)
from lbx_printer.services import LabelTemplateService

pytestmark = pytest.mark.unit


@pytest.fixture
def service(tmp_path: Path, address_lbx: Path) -> LabelTemplateService:
    target = tmp_path / "templates"
    target.mkdir()
    (target / "address.lbx").write_bytes(address_lbx.read_bytes())

    return LabelTemplateService(target)


def test_list_describes_templates_and_their_fields(
    service: LabelTemplateService,
) -> None:
    templates = service.list()

    assert [template.name for template in templates] == ["address"]
    assert templates[0].template == "address.lbx"
    assert set(templates[0].fields) == {"address", "title"}
    assert templates[0].description == "Brother QL-1110NWB"


def test_get_accepts_a_name_or_a_file_name(service: LabelTemplateService) -> None:
    assert service.get("address").name == "address"
    assert service.get("address.lbx").name == "address"


def test_exists_reports_missing_templates(service: LabelTemplateService) -> None:
    assert service.exists("address") is True
    assert service.exists("nope") is False


def test_resolve_path_raises_for_missing_templates(
    service: LabelTemplateService,
) -> None:
    with pytest.raises(LabelTemplateNotFoundError):
        service.resolve_path("nope")


def test_import_copies_the_file_and_infers_fields(
    service: LabelTemplateService, address_lbx: Path
) -> None:
    imported = service.import_file(address_lbx, name="shipping", description="Ship")

    assert imported.name == "shipping"
    assert imported.template == "shipping.lbx"
    assert imported.description == "Ship"
    assert set(imported.fields) == {"address", "title"}
    assert (service.template_dir / "shipping.lbx").is_file()


def test_import_rejects_duplicate_names(
    service: LabelTemplateService, address_lbx: Path
) -> None:
    with pytest.raises(LabelAlreadyExistsError):
        service.import_file(address_lbx, name="address")


def test_import_rejects_missing_sources(
    service: LabelTemplateService, tmp_path: Path
) -> None:
    with pytest.raises(LabelTemplateNotFoundError):
        service.import_file(tmp_path / "nope.lbx")


def test_import_rejects_corrupted_archives(
    service: LabelTemplateService, tmp_path: Path
) -> None:
    broken = tmp_path / "broken.lbx"
    broken.write_bytes(b"not a zip")

    with pytest.raises(zipfile.BadZipFile):
        service.import_file(broken, name="broken")

    assert not (service.template_dir / "broken.lbx").exists()


def test_delete_removes_the_file(service: LabelTemplateService) -> None:
    service.delete("address")

    assert service.exists("address") is False


def test_delete_reports_missing_templates(service: LabelTemplateService) -> None:
    service.delete("address")

    with pytest.raises(LabelTemplateNotFoundError):
        service.delete("address")


def test_list_of_a_missing_directory_is_empty(tmp_path: Path) -> None:
    assert LabelTemplateService(tmp_path / "absent").list() == []
