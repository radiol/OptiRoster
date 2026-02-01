"""Tests for specified-dates editor pure logic helpers.

Covers:
- get_default_month (next-month calculation)
- is_in_displayed_month (cell visibility check)
"""

from __future__ import annotations

from datetime import date

from src.gui.editors.specified_editor import (
    get_default_month,
    is_in_displayed_month,
)


# -- get_default_month -------------------------------------------------------
class TestGetDefaultMonth:
    def test_january_to_february(self):
        assert get_default_month(date(2026, 1, 31)) == (2026, 2)

    def test_mid_year(self):
        assert get_default_month(date(2026, 6, 15)) == (2026, 7)

    def test_december_to_next_year_january(self):
        assert get_default_month(date(2026, 12, 15)) == (2027, 1)

    def test_december_31(self):
        assert get_default_month(date(2026, 12, 31)) == (2027, 1)

    def test_february_to_march(self):
        assert get_default_month(date(2026, 2, 28)) == (2026, 3)


# -- is_in_displayed_month ---------------------------------------------------
class TestIsInDisplayedMonth:
    def test_same_month_returns_true(self):
        assert is_in_displayed_month(2026, 3, 2026, 3) is True

    def test_previous_month_returns_false(self):
        assert is_in_displayed_month(2026, 2, 2026, 3) is False

    def test_next_month_returns_false(self):
        assert is_in_displayed_month(2026, 4, 2026, 3) is False

    def test_different_year_returns_false(self):
        assert is_in_displayed_month(2025, 12, 2026, 1) is False
