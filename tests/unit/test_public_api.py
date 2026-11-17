"""Unit tests for localisation and the public API surface."""

from __future__ import annotations

import os

import pytest

import brother_bridge
from brother_bridge.exceptions import LabelTemplateNotFoundError
from brother_bridge.i18n import (
    DEFAULT_LOCALE,
    LOCALE_ENVIRONMENT_VARIABLE,
    available_locales,
    get_locale,
    set_locale,
    translate,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def restore_locale():
    previous = get_locale()
    yield
    set_locale(previous)


def test_default_locale_ships_english_messages() -> None:
    assert DEFAULT_LOCALE == "en"
    assert "en" in available_locales()
    assert "fr" in available_locales()


def test_translate_substitutes_placeholders() -> None:
    set_locale("en")

    assert "address.lbx" in translate("template_not_found", target="address.lbx")


def test_french_catalogue_is_used_after_set_locale() -> None:
    set_locale("fr")

    message = translate("template_not_found", target="address.lbx")

    assert "Modèle" in message
    assert "address.lbx" in message


def test_unknown_locale_falls_back_to_english() -> None:
    set_locale("xx-YY")

    assert get_locale() == DEFAULT_LOCALE


def test_unknown_message_key_returns_the_key() -> None:
    assert translate("no_such_message") == "no_such_message"


def test_exception_messages_follow_the_locale() -> None:
    set_locale("fr")

    with pytest.raises(LabelTemplateNotFoundError) as excinfo:
        raise LabelTemplateNotFoundError("missing.lbx")

    assert "introuvable" in str(excinfo.value)


def test_locale_can_be_reset_to_environment_default() -> None:
    set_locale("fr")
    set_locale(None)

    assert (
        get_locale()
        == os.environ.get(LOCALE_ENVIRONMENT_VARIABLE, DEFAULT_LOCALE).lower()
    )


def test_public_api_exports_are_importable() -> None:
    for name in brother_bridge.__all__:
        assert hasattr(brother_bridge, name), f"missing public attribute: {name}"
