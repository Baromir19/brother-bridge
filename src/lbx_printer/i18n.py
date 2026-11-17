"""Dependency-free localisation of user-facing messages.

Only messages that reach end users (exception text) are translated. Log
records stay in English because they target developers and operators.

The active locale is resolved from, in order:

1. :func:`set_locale`,
2. the ``LBX_PRINTER_LOCALE`` environment variable,
3. :data:`DEFAULT_LOCALE`.

Unknown locales fall back to English, so a caller can never end up without a
message.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_LOCALE = "en"
LOCALE_ENVIRONMENT_VARIABLE = "LBX_PRINTER_LOCALE"

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "missing_dependency": "Required dependency '{dependency}' is not installed.",
        "template_not_found": "Label template not found: {target}",
        "template_exists": "A label template named '{name}' already exists.",
        "field_not_found": "Field '{name}' does not exist in the label template.",
        "invalid_field_type": (
            "Field '{name}' has type '{object_type}' and cannot receive a text value."
        ),
        "data_missing": "Missing values for template fields: {fields}",
        "document_not_open": (
            "The label document is not open. Call open() or use the document "
            "as a context manager."
        ),
        "label_not_resolved": (
            "No brother_ql label identifier has been resolved for this document."
        ),
        "unsupported_label": (
            "No brother_ql label matches {width} x {height} mm "
            "(continuous={continuous}); closest candidate '{name}' is "
            "{distance:.2f} mm away, above the {threshold} mm tolerance."
        ),
        "unsupported_label_kind": (
            "No {kind} label is available in brother_ql for {width} x {height} mm."
        ),
        "bpac_unavailable": (
            "b-PAC is unavailable: {reason}. Install the Brother b-PAC SDK and "
            "make sure the COM class 'bpac.Document' is registered."
        ),
        "config_invalid": "Invalid configuration value for '{field}': {reason}",
    },
    "fr": {
        "missing_dependency": (
            "La dépendance obligatoire '{dependency}' n'est pas installée."
        ),
        "template_not_found": "Modèle d'étiquette introuvable : {target}",
        "template_exists": "Un modèle d'étiquette nommé '{name}' existe déjà.",
        "field_not_found": "Le champ '{name}' n'existe pas dans le modèle d'étiquette.",
        "invalid_field_type": (
            "Le champ '{name}' est de type '{object_type}' et ne peut pas recevoir "
            "de valeur textuelle."
        ),
        "data_missing": "Valeurs manquantes pour les champs du modèle : {fields}",
        "document_not_open": (
            "Le document d'étiquette n'est pas ouvert. Appelez open() ou utilisez "
            "le document comme gestionnaire de contexte."
        ),
        "label_not_resolved": (
            "Aucun identifiant de bande brother_ql n'a été résolu pour ce document."
        ),
        "unsupported_label": (
            "Aucune bande brother_ql ne correspond à {width} x {height} mm "
            "(continue={continuous}) ; la meilleure candidate '{name}' est à "
            "{distance:.2f} mm, au-delà de la tolérance de {threshold} mm."
        ),
        "unsupported_label_kind": (
            "Aucune bande de type {kind} n'est disponible dans brother_ql pour "
            "{width} x {height} mm."
        ),
        "bpac_unavailable": (
            "b-PAC est indisponible : {reason}. Installez le SDK Brother b-PAC et "
            "vérifiez que la classe COM 'bpac.Document' est enregistrée."
        ),
        "config_invalid": "Valeur de configuration invalide pour '{field}' : {reason}",
    },
}

_locale: str = os.environ.get(LOCALE_ENVIRONMENT_VARIABLE, DEFAULT_LOCALE).lower()


def available_locales() -> tuple[str, ...]:
    """Return the locales that ship with built-in messages."""
    return tuple(sorted(_MESSAGES))


def get_locale() -> str:
    """Return the active locale code."""
    return _locale


def set_locale(locale: str | None) -> None:
    """Select the locale used by :func:`translate`.

    Args:
        locale: Locale code such as ``"en"`` or ``"fr"``. ``None`` restores the
            environment-derived default. Unsupported codes fall back to
            :data:`DEFAULT_LOCALE`.
    """
    global _locale

    if locale is None:
        _locale = os.environ.get(LOCALE_ENVIRONMENT_VARIABLE, DEFAULT_LOCALE).lower()
        return

    code = locale.replace("_", "-").split("-")[0].lower()
    _locale = code if code in _MESSAGES else DEFAULT_LOCALE


def translate(key: str, /, **values: Any) -> str:
    """Return the message registered under ``key`` for the active locale.

    Args:
        key: Message identifier.
        **values: Placeholders substituted into the message.

    Returns:
        The formatted message, or ``key`` itself when it is unknown.
    """
    catalog = _MESSAGES.get(_locale, _MESSAGES[DEFAULT_LOCALE])
    template = catalog.get(key) or _MESSAGES[DEFAULT_LOCALE].get(key)

    if template is None:
        return key

    return template.format(**values)


__all__ = [
    "DEFAULT_LOCALE",
    "LOCALE_ENVIRONMENT_VARIABLE",
    "available_locales",
    "get_locale",
    "set_locale",
    "translate",
]
