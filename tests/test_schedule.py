"""Schedule resolution.

This is the most intricate logic in the codebase — half-open intervals,
windows crossing midnight, and a special case for 23:59 — and it is pure,
so it is where tests are worth the most.
"""
from types import SimpleNamespace

import pytest

import app as lumina


def sched(start, end, days="mon", sid="s1", name="Test"):
    """A stand-in for a Schedule row; the functions only read these fields."""
    return SimpleNamespace(
        id=sid, name=name, start_time=start, end_time=end, days=days
    )


# ── parse_hhmm_to_min ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("00:00", 0),
    ("09:30", 570),
    ("23:59", 1439),
])
def test_parse_hhmm_accepts_valid_times(value, expected):
    assert lumina.parse_hhmm_to_min(value) == expected


@pytest.mark.parametrize("value", [
    "24:00",    # hour out of range
    "12:60",    # minute out of range
    "9:30",     # not zero-padded
    "0930",     # missing separator
    "",
    None,
    12345,
])
def test_parse_hhmm_rejects_invalid_times(value):
    assert lumina.parse_hhmm_to_min(value) is None


# ── normalize_days ────────────────────────────────────────────────────────────

def test_normalize_days_preserves_order_and_deduplicates():
    assert lumina.normalize_days("mon,wed,mon,fri") == "mon,wed,fri"


def test_normalize_days_is_case_and_space_insensitive():
    assert lumina.normalize_days(" MON , Tue ") == "mon,tue"


@pytest.mark.parametrize("value", ["", "funday", "mon,notaday", None, 7])
def test_normalize_days_rejects_invalid_input(value):
    assert lumina.normalize_days(value) is None


# ── schedule_to_day_intervals ─────────────────────────────────────────────────

def test_simple_window_is_half_open():
    # 09:00-17:00 on Monday (day 0)
    intervals = lumina.schedule_to_day_intervals(540, 1020, "mon")
    assert intervals == [(0, 540, 1020)]


def test_equal_start_and_end_covers_the_whole_day():
    intervals = lumina.schedule_to_day_intervals(600, 600, "tue")
    assert intervals == [(1, 0, 1440)]


def test_2359_is_treated_as_end_of_day():
    # Without the special case this would stop a minute early.
    intervals = lumina.schedule_to_day_intervals(0, 1439, "wed")
    assert intervals == [(2, 0, 1440)]


def test_overnight_window_splits_across_midnight():
    # 23:00-02:00 on Sunday should also cover the small hours of Monday.
    intervals = lumina.schedule_to_day_intervals(1380, 120, "sun")
    assert sorted(intervals) == sorted([(6, 1380, 1440), (0, 0, 120)])


def test_overnight_window_wraps_from_sunday_to_monday():
    intervals = lumina.schedule_to_day_intervals(1380, 120, "sun")
    assert (0, 0, 120) in intervals, "Sunday night must spill into Monday"


def test_multiple_days_produce_one_interval_each():
    intervals = lumina.schedule_to_day_intervals(540, 1020, "mon,fri")
    assert intervals == [(0, 540, 1020), (4, 540, 1020)]


def test_invalid_days_yield_no_intervals():
    assert lumina.schedule_to_day_intervals(540, 1020, "notaday") is None


# ── intervals_overlap ─────────────────────────────────────────────────────────

def test_touching_intervals_do_not_overlap():
    # 10:00-12:00 and 12:00-14:00 are adjacent, not overlapping. This is the
    # whole point of using half-open intervals.
    assert not lumina.intervals_overlap(600, 720, 720, 840)


def test_partially_overlapping_intervals_overlap():
    assert lumina.intervals_overlap(600, 780, 720, 840)


def test_contained_interval_overlaps():
    assert lumina.intervals_overlap(600, 900, 700, 800)


def test_disjoint_intervals_do_not_overlap():
    assert not lumina.intervals_overlap(600, 660, 800, 900)


# ── find_overlapping_schedule ─────────────────────────────────────────────────

def test_finds_a_clashing_schedule_on_the_same_day():
    existing = [sched("09:00", "17:00", "mon", sid="a")]
    candidate = lumina.schedule_to_day_intervals(600, 720, "mon")
    assert lumina.find_overlapping_schedule(candidate, existing).id == "a"


def test_ignores_schedules_on_other_days():
    existing = [sched("09:00", "17:00", "tue", sid="a")]
    candidate = lumina.schedule_to_day_intervals(600, 720, "mon")
    assert lumina.find_overlapping_schedule(candidate, existing) is None


def test_back_to_back_schedules_are_allowed():
    existing = [sched("09:00", "12:00", "mon", sid="a")]
    candidate = lumina.schedule_to_day_intervals(720, 1020, "mon")  # 12:00-17:00
    assert lumina.find_overlapping_schedule(candidate, existing) is None


def test_overnight_schedule_clashes_with_next_morning():
    existing = [sched("23:00", "02:00", "sun", sid="night")]
    candidate = lumina.schedule_to_day_intervals(0, 60, "mon")  # Monday 00:00-01:00
    assert lumina.find_overlapping_schedule(candidate, existing).id == "night"


# ── schedule_match_interval_for_now ───────────────────────────────────────────

def test_matches_inside_the_window():
    assert lumina.schedule_match_interval_for_now(
        sched("09:00", "17:00", "mon"), 0, 600
    ) == (540, 1020)


def test_start_boundary_is_inclusive():
    assert lumina.schedule_match_interval_for_now(
        sched("09:00", "17:00", "mon"), 0, 540
    ) is not None


def test_end_boundary_is_exclusive():
    assert lumina.schedule_match_interval_for_now(
        sched("09:00", "17:00", "mon"), 0, 1020
    ) is None


def test_does_not_match_on_a_different_day():
    assert lumina.schedule_match_interval_for_now(
        sched("09:00", "17:00", "mon"), 3, 600
    ) is None


def test_overnight_window_matches_after_midnight():
    # 23:00 Sunday to 02:00 Monday; check 01:00 on Monday (day 0).
    assert lumina.schedule_match_interval_for_now(
        sched("23:00", "02:00", "sun"), 0, 60
    ) is not None


def test_malformed_times_never_match():
    assert lumina.schedule_match_interval_for_now(
        sched("nope", "17:00", "mon"), 0, 600
    ) is None
