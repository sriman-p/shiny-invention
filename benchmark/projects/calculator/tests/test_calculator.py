"""Fast first-pass tests for calculator requirements REQ-001–REQ-005."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calc import Calculator  # noqa: E402


@pytest.fixture
def calc():
    return Calculator()


def test_addition_happy_path(calc):
    assert calc.add(2, 3) == 5
    assert calc.add(-1, -2) == -3
    assert calc.add(0.1, 0.2) == pytest.approx(0.3)


def test_subtraction_happy_path(calc):
    assert calc.subtract(5, 3) == 2
    assert calc.subtract(2, 5) == -3


def test_multiplication_happy_path(calc):
    assert calc.multiply(3, 4) == 12
    assert calc.multiply(7, 0) == 0


def test_division_happy_path(calc):
    assert calc.divide(10, 2) == 5
    with pytest.raises(ZeroDivisionError):
        calc.divide(1, 0)


def test_input_validation(calc):
    with pytest.raises(ValueError):
        calc.add("2", 3)
    with pytest.raises(TypeError):
        calc.add(None, 1)
