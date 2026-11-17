"""Unit tests for the logging helpers."""

from __future__ import annotations

import logging

import pytest

from lbx_printer.logging import (
    PACKAGE_LOGGER_NAME,
    configure_logging,
    get_logger,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_package_logger():
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    original_level = logger.level
    original_handlers = list(logger.handlers)
    logger.handlers = [
        handler
        for handler in logger.handlers
        if not isinstance(handler, logging.StreamHandler)
    ]

    yield

    logger.handlers = original_handlers
    logger.setLevel(original_level)


def test_package_logger_is_silent_by_default() -> None:
    handlers = logging.getLogger(PACKAGE_LOGGER_NAME).handlers

    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_get_logger_prefixes_child_loggers() -> None:
    assert get_logger("lbx_printer.lbx.parser").name == "lbx_printer.lbx.parser"
    assert get_logger("lbx.writer").name == "lbx_printer.lbx.writer"
    assert get_logger("").name == PACKAGE_LOGGER_NAME


def test_configure_logging_installs_one_stream_handler(capsys) -> None:
    configure_logging("INFO")
    configure_logging("DEBUG")
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)

    stream_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
    ]

    assert len(stream_handlers) == 1
    assert logger.level == logging.DEBUG

    logger.info("hello from the package")
    assert "hello from the package" in capsys.readouterr().err


def test_logger_hierarchy_keeps_child_levels() -> None:
    logger = get_logger("lbx_printer.services")

    assert logger.parent is logging.getLogger(PACKAGE_LOGGER_NAME)
