"""Tests for ``agentic_calendar.common.ids``."""

from __future__ import annotations

import pytest

from agentic_calendar.common.ids import (
    DeterministicIdGenerator,
    IdGenerator,
    UuidIdGenerator,
)


def test_uuid_generator_format() -> None:
    gen = UuidIdGenerator(hex_chars=8)
    ident = gen.new_id("run")
    assert ident.startswith("run_")
    suffix = ident.removeprefix("run_")
    assert len(suffix) == 8
    int(suffix, 16)


def test_uuid_generator_unique() -> None:
    gen = UuidIdGenerator()
    ids = {gen.new_id("plan") for _ in range(100)}
    assert len(ids) == 100


def test_uuid_generator_validates_hex_chars() -> None:
    with pytest.raises(ValueError):
        UuidIdGenerator(hex_chars=2)
    with pytest.raises(ValueError):
        UuidIdGenerator(hex_chars=64)


def test_uuid_generator_validates_prefix() -> None:
    gen = UuidIdGenerator()
    with pytest.raises(ValueError):
        gen.new_id("")


def test_deterministic_generator_counter_per_prefix() -> None:
    gen = DeterministicIdGenerator(digits=3)
    assert gen.new_id("run") == "run_001"
    assert gen.new_id("run") == "run_002"
    assert gen.new_id("plan") == "plan_001"
    assert gen.new_id("run") == "run_003"


def test_deterministic_generator_two_instances_match() -> None:
    a = DeterministicIdGenerator()
    b = DeterministicIdGenerator()
    seq_a = [a.new_id("task") for _ in range(5)]
    seq_b = [b.new_id("task") for _ in range(5)]
    assert seq_a == seq_b


def test_deterministic_generator_satisfies_protocol() -> None:
    assert isinstance(DeterministicIdGenerator(), IdGenerator)
    assert isinstance(UuidIdGenerator(), IdGenerator)


def test_deterministic_generator_validates_digits() -> None:
    with pytest.raises(ValueError):
        DeterministicIdGenerator(digits=0)
    with pytest.raises(ValueError):
        DeterministicIdGenerator(digits=11)
