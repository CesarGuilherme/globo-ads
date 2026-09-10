"""Date-window tests. Same off-by-ones the DSP connector locked down."""
from datetime import date, datetime, timedelta, timezone

import pytest

from source_globo_ads.auth import BareTokenAuthenticator
from source_globo_ads.streams.items import DigitalItems

TODAY = date(2026, 6, 1)
YESTERDAY = TODAY - timedelta(days=1)
DEFAULT_START = date(2023, 1, 1)


def build(**kwargs):
    stream = DigitalItems(
        authenticator=BareTokenAuthenticator("tok"),
        cod_client=258469,
        **kwargs,
    )
    stream._today = lambda: TODAY
    return stream


def windows(stream):
    return [(s.isoformat(), e.isoformat()) for s, e in stream._windows()]


def test_end_date_is_yesterday_never_today():
    stream = build(start_date="2026-05-28")
    assert stream._end_date() == YESTERDAY
    assert windows(stream)[-1][1] == "2026-05-31"


def test_configured_end_date_is_still_capped_at_yesterday():
    stream = build(start_date="2026-05-28", end_date="2026-12-31")
    assert stream._end_date() == YESTERDAY


def test_resume_is_at_the_cursor_not_cursor_plus_one():
    stream = build(start_date="2026-01-01", lookback_window_days=0)
    stream.state = {"date": "2026-05-20"}
    assert stream._start_date() == date(2026, 5, 20)
    assert windows(stream)[0][0] == "2026-05-20"


def test_lookback_window_re_reads_trailing_days():
    stream = build(start_date="2026-01-01", lookback_window_days=7)
    stream.state = {"date": "2026-05-20"}
    assert stream._start_date() == date(2026, 5, 13)


def test_lookback_never_reaches_before_the_configured_start():
    stream = build(start_date="2026-05-18", lookback_window_days=30)
    stream.state = {"date": "2026-05-20"}
    assert stream._start_date() == date(2026, 5, 18)


def test_empty_start_date_defaults_to_2023_01_01():
    stream = build()
    assert stream._start_date() == DEFAULT_START


def test_up_to_date_cursor_with_zero_lookback_produces_no_slices():
    stream = build(start_date="2026-01-01", lookback_window_days=0)
    stream.state = {"date": TODAY.isoformat()}
    assert windows(stream) == []


def test_windows_are_contiguous_and_sized_to_config():
    stream = build(start_date="2026-04-01", window_in_days=31)
    w = windows(stream)
    assert w[0] == ("2026-04-01", "2026-05-01")
    assert w[1][0] == "2026-05-02"
    for (_, prev_end), (next_start, _) in zip(w, w[1:]):
        assert date.fromisoformat(next_start) - date.fromisoformat(prev_end) == timedelta(days=1)
    assert w[-1][1] == YESTERDAY.isoformat()


def test_today_is_sao_paulo_not_utc(monkeypatch):
    """02:00 UTC on June 1 is still May 31 in America/Sao_Paulo."""
    stream = DigitalItems(authenticator=BareTokenAuthenticator("tok"), cod_client=258469)
    frozen = datetime(2026, 6, 1, 2, 0, tzinfo=timezone.utc)

    class _Dt:
        @staticmethod
        def now(tz=None):
            return frozen.astimezone(tz) if tz else frozen

    monkeypatch.setattr("source_globo_ads.streams.base.datetime", _Dt)
    assert stream._today() == date(2026, 5, 31)
    assert stream._end_date() == date(2026, 5, 30)
