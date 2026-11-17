"""Unit tests for configuration handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from lbx_printer.config import (
    DEFAULT_DPI,
    DEFAULT_HOST,
    DEFAULT_MODEL,
    ENV_CUT,
    ENV_DPI,
    ENV_HOST,
    ENV_LABEL,
    ENV_MODEL,
    ENV_PORT,
    ENV_TEMPLATE_DIR,
    PrinterConfig,
)
from lbx_printer.exceptions import ConfigurationError

pytestmark = pytest.mark.unit


def test_defaults_match_brother_ql_defaults() -> None:
    config = PrinterConfig()

    assert config.host == DEFAULT_HOST
    assert config.model == DEFAULT_MODEL
    assert config.dpi == DEFAULT_DPI
    assert config.label is None


def test_from_env_reads_every_supported_variable() -> None:
    env = {
        ENV_HOST: "192.0.2.5",
        ENV_MODEL: "QL-820NWB",
        ENV_LABEL: "62",
        ENV_PORT: "9101",
        ENV_CUT: "false",
        ENV_DPI: "600",
        ENV_TEMPLATE_DIR: "labels",
    }

    config = PrinterConfig.from_env(env)

    assert config.host == "192.0.2.5"
    assert config.model == "QL-820NWB"
    assert config.label == "62"
    assert config.port == 9101
    assert config.cut is False
    assert config.dpi == 600
    assert config.template_dir == Path("labels")


def test_from_env_ignores_unset_variables() -> None:
    assert PrinterConfig.from_env({}) == PrinterConfig()


def test_from_env_treats_an_empty_label_as_auto_detection() -> None:
    config = PrinterConfig.from_env({ENV_LABEL: ""})

    assert config.label is None


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        (ENV_PORT, "not-a-port"),
        (ENV_CUT, "maybe"),
        (ENV_DPI, "many"),
    ],
)
def test_from_env_rejects_malformed_values(variable: str, value: str) -> None:
    with pytest.raises(ConfigurationError):
        PrinterConfig.from_env({variable: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", " "),
        ("model", ""),
        ("port", 0),
        ("port", 70000),
        ("dpi", 0),
        ("threshold", 101),
        ("label", "  "),
    ],
)
def test_validation_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ConfigurationError):
        PrinterConfig(**{field: value})  # type: ignore[arg-type]


def test_with_overrides_returns_a_new_configuration() -> None:
    base = PrinterConfig()
    tuned = base.with_overrides(host="192.0.2.20", dpi=600)

    assert tuned.host == "192.0.2.20"
    assert tuned.dpi == 600
    assert base.host == DEFAULT_HOST

    with pytest.raises(TypeError):
        base.with_overrides(unknown="value")


def test_to_dict_is_json_friendly() -> None:
    config = PrinterConfig(template_dir=Path("labels"))

    assert config.to_dict()["template_dir"] == "labels"
    assert PrinterConfig().to_dict()["template_dir"] is None
