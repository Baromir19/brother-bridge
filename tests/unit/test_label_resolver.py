"""Unit tests for tape resolution against the ``brother_ql`` catalogue."""

from __future__ import annotations

import pytest

from brother_bridge.lbx.model import PaperSpec
from brother_bridge.printers.label_resolver import (
    MAX_DISTANCE_MM,
    BrotherQlLabelResolver,
    UnsupportedLabelError,
)

pytestmark = pytest.mark.unit


def paper(width_pt: float, height_pt: float, *, auto_length: bool) -> PaperSpec:
    return PaperSpec(width_pt=width_pt, height_pt=height_pt, auto_length=auto_length)


def test_resolves_continuous_tape_by_width() -> None:
    resolver = BrotherQlLabelResolver()

    assert resolver.resolve(paper(175.7, 8503.9, auto_length=True)) == "62"


def test_resolves_die_cut_label_by_width_and_height() -> None:
    resolver = BrotherQlLabelResolver()

    assert resolver.resolve(paper(293.8, 465.8, auto_length=False)) == "103x164"


def test_resolution_tolerates_rounding_errors() -> None:
    resolver = BrotherQlLabelResolver()

    assert resolver.resolve(paper(176.5, 100.0, auto_length=True)) == "62"


def test_unknown_size_raises_unsupported_label() -> None:
    resolver = BrotherQlLabelResolver()

    with pytest.raises(UnsupportedLabelError) as excinfo:
        resolver.resolve(paper(500.0, 500.0, auto_length=True))

    assert "62" not in str(excinfo.value)


def test_unsupported_label_is_a_value_error() -> None:
    assert issubclass(UnsupportedLabelError, ValueError)


def test_tolerance_is_two_millimetres() -> None:
    assert MAX_DISTANCE_MM == 2.0


def test_resolver_instances_share_the_same_geometry_set() -> None:
    first = BrotherQlLabelResolver()
    second = BrotherQlLabelResolver()

    assert first._labels == second._labels
