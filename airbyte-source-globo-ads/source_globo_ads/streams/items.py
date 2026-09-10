import json
import logging
from datetime import date, timedelta
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.core import CheckpointMixin

from .base import (
    DATE_FMT,
    DEFAULT_START_DATE,
    DEFAULT_WINDOW_IN_DAYS,
    GloboAdsStream,
    _parse_date,
    flatten,
)

logger = logging.getLogger("airbyte")


class DigitalItems(GloboAdsStream, CheckpointMixin):
    """POST /digital/items — incremental, no PK, append at the destination."""

    name = "digital_items"
    cursor_field = "date"

    def __init__(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lookback_window_days: int = 7,
        window_in_days: int = DEFAULT_WINDOW_IN_DAYS,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._configured_start_date = start_date or DEFAULT_START_DATE
        self._configured_end_date = end_date
        self._lookback_window_days = lookback_window_days
        self._window_in_days = window_in_days
        self._state: MutableMapping[str, Any] = {}

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @state.setter
    def state(self, value: MutableMapping[str, Any]) -> None:
        self._state = value or {}

    def path(self, **kwargs: Any) -> str:
        return "digital/items"

    def _end_date(self) -> date:
        yesterday = self._today() - timedelta(days=1)
        if self._configured_end_date:
            return min(_parse_date(self._configured_end_date), yesterday)
        return yesterday

    def _start_date(self) -> date:
        start = _parse_date(self._configured_start_date)
        cursor = self._state.get(self.cursor_field)
        if cursor:
            resume = _parse_date(str(cursor)[:10]) - timedelta(days=self._lookback_window_days)
            start = max(start, resume)
        return start

    def _windows(self) -> Iterable[Tuple[date, date]]:
        end = self._end_date()
        cursor = self._start_date()
        while cursor <= end:
            window_end = min(cursor + timedelta(days=self._window_in_days - 1), end)
            yield cursor, window_end
            cursor = window_end + timedelta(days=1)

    def stream_slices(
        self,
        sync_mode: SyncMode,
        cursor_field: Optional[List[str]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Optional[Mapping[str, Any]]]:
        if stream_state:
            self.state = stream_state
        for window_start, window_end in self._windows():
            yield {
                "start_date": window_start.strftime(DATE_FMT),
                "end_date": window_end.strftime(DATE_FMT),
            }

    def request_body_json(
        self,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        stream_slice = stream_slice or {}
        page = (next_page_token or {}).get("page", 0)
        return {
            "codClient": self._cod_client,
            "startDate": stream_slice["start_date"],
            "endDate": stream_slice["end_date"],
            "page": page,
            "size": self.page_size,
        }

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        body = response.json()
        content = body.get("content") or []
        if body.get("last") or not content:
            return None
        try:
            sent = json.loads(response.request.body or b"{}")
        except (ValueError, TypeError):
            sent = {}
        current = sent.get("page", 0)
        total_pages = body.get("totalPages") or 1
        if current + 1 >= total_pages:
            return None
        return {"page": current + 1}

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> Iterable[Mapping[str, Any]]:
        body = response.json()
        for rec in body.get("content") or []:
            flat = flatten(rec)
            date_val = flat.get(self.cursor_field)
            if date_val:
                self._advance_state(str(date_val)[:10])
            yield flat

    def _advance_state(self, record_date: str) -> None:
        if record_date > self._state.get(self.cursor_field, ""):
            self._state[self.cursor_field] = record_date
