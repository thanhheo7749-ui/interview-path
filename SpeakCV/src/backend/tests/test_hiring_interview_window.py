"""Pure unit tests of the window helper: no DB, no fixtures."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.hiring import interview_window


def job(enabled=True, start=None, end=None, tz=None):
    return SimpleNamespace(scheduling_enabled=enabled, interview_window_start=start,
                           interview_window_end=end, interview_window_timezone=tz)


# is_open


def test_is_open_disabled_is_always_open():
    assert interview_window.is_open(job(enabled=False), datetime(2026, 1, 1))
    assert interview_window.is_open(job(enabled=False, start=None, end=None), datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_is_open_naive_bounds_and_aware_now():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 3)
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert interview_window.is_open(job(start=start, end=end), now)


def test_is_open_aware_bounds_and_naive_now():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 3, tzinfo=timezone.utc)
    now = datetime(2026, 1, 2)
    assert interview_window.is_open(job(start=start, end=end), now)


def test_is_open_edges_are_closed_interval():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 3)
    assert interview_window.is_open(job(start=start, end=end), start)
    assert interview_window.is_open(job(start=start, end=end), end)


def test_is_open_outside_bounds():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 3)
    assert not interview_window.is_open(job(start=start, end=end), datetime(2025, 12, 31))
    assert not interview_window.is_open(job(start=start, end=end), datetime(2026, 1, 4))


# check


def test_check_disabled_passes_regardless_of_bounds():
    interview_window.check(False, None, None, None)
    interview_window.check(False, datetime(2026, 1, 3), datetime(2026, 1, 1), "not-a-zone")


def test_check_enabled_valid_passes():
    interview_window.check(True, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 3, tzinfo=timezone.utc), "UTC")
    interview_window.check(True, datetime(2026, 1, 1), datetime(2026, 1, 3), None)


def test_check_enabled_missing_start_raises_422():
    with pytest.raises(HTTPException) as exc:
        interview_window.check(True, None, datetime(2026, 1, 3), None)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == interview_window.INVALID_INTERVIEW_WINDOW


def test_check_enabled_missing_end_raises_422():
    with pytest.raises(HTTPException) as exc:
        interview_window.check(True, datetime(2026, 1, 1), None, None)
    assert exc.value.status_code == 422


def test_check_enabled_start_equals_end_raises_422():
    same = datetime(2026, 1, 1)
    with pytest.raises(HTTPException):
        interview_window.check(True, same, same, None)


def test_check_enabled_start_after_end_raises_422():
    with pytest.raises(HTTPException):
        interview_window.check(True, datetime(2026, 1, 3), datetime(2026, 1, 1), None)


def test_check_bad_timezone_name_raises_422():
    with pytest.raises(HTTPException) as exc:
        interview_window.check(True, datetime(2026, 1, 1), datetime(2026, 1, 3), "Not/AZone")
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == interview_window.INVALID_INTERVIEW_WINDOW


# to_utc / as_aware


def test_to_utc_converts_aware_and_passes_naive_through():
    aware = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    assert interview_window.to_utc(aware) == datetime(2026, 1, 1, 10)
    naive = datetime(2026, 1, 1, 10)
    assert interview_window.to_utc(naive) == naive
    assert interview_window.to_utc(None) is None


def test_as_aware_adds_utc_and_passes_aware_through():
    naive = datetime(2026, 1, 1, 10)
    assert interview_window.as_aware(naive) == datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    assert interview_window.as_aware(None) is None


# payload


def test_payload_is_none_when_disabled():
    assert interview_window.payload(job(enabled=False)) is None


def test_payload_has_start_end_timezone_when_enabled():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 3)
    result = interview_window.payload(job(start=start, end=end, tz="Asia/Ho_Chi_Minh"))
    assert result == {
        "start": datetime(2026, 1, 1, tzinfo=timezone.utc), "end": datetime(2026, 1, 3, tzinfo=timezone.utc),
        "timezone": "Asia/Ho_Chi_Minh",
    }
