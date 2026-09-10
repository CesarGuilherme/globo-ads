import logging
from datetime import timedelta
from typing import Any, Iterable, List, Mapping, Optional, Tuple

import requests
from airbyte_cdk.models import FailureType, SyncMode
from airbyte_cdk.sources.streams.http.error_handlers import ErrorResolution, HttpStatusErrorHandler, ResponseAction

from .base import DATE_FMT, DEFAULT_START_DATE, GloboAdsStream
from .items import DigitalItems

logger = logging.getLogger("airbyte")

DEMO_PARENT_FIELDS = [
    "startDate", "endDate", "project", "codCampaign", "campaign",
    "codClient", "nameClient", "codAgency", "nameAgency",
]
DEFAULT_DEMOGRAPHIC_LOOKBACK_DAYS = 190


def select_demographic_candidates(item_rows: Iterable[Mapping[str, Any]], cutoff: str) -> List[Tuple[str, str]]:
    """(codCampaing, campaign) pairs that are not DAI-A and last delivered on/after cutoff."""
    latest: dict = {}
    for rec in item_rows:
        if rec.get("campaignType") == "DAI-A":
            continue
        day = rec.get("date")
        if not day or str(day)[:10] < cutoff:
            continue
        cod = rec.get("codCampaing")
        name = rec.get("campaign")
        if not cod or not name:
            continue
        prev = latest.get(cod)
        if prev is None or str(day)[:10] > prev[0]:
            latest[str(cod)] = (str(day)[:10], str(name))
    return [(cod, name) for cod, (_, name) in sorted(latest.items())]


def explode_demographic(entry: Mapping[str, Any]) -> List[dict]:
    parent = {f: entry.get(f) for f in DEMO_PARENT_FIELDS}
    rows = []
    for arr in ("ages", "genders", "region"):
        for item in entry.get(arr) or []:
            rows.append({**parent, **item})
    return rows


class DemographicErrorHandler(HttpStatusErrorHandler):
    """A 504 on one campaign must not fail the stream; extract.py skipped those too."""

    def interpret_response(self, response_or_exception: Optional[Any] = None) -> ErrorResolution:
        if isinstance(response_or_exception, requests.Response) and response_or_exception.status_code == 504:
            logger.warning("digital/demographic HTTP 504 — skipping this campaign")
            return ErrorResolution(
                response_action=ResponseAction.IGNORE,
                failure_type=FailureType.transient_error,
                error_message="Globo Ads demographic 504 skipped",
            )
        return super().interpret_response(response_or_exception)


class DigitalDemographic(GloboAdsStream):
    """POST /digital/demographic — one call per in-window non-DAI-A campaign."""

    name = "digital_demographic"

    def __init__(
        self,
        *,
        items: DigitalItems,
        demographic_lookback_days: int = DEFAULT_DEMOGRAPHIC_LOOKBACK_DAYS,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._items = items
        self._lookback_days = demographic_lookback_days
        self._configured_start_date = start_date or DEFAULT_START_DATE
        self._configured_end_date = end_date

    def get_error_handler(self) -> HttpStatusErrorHandler:
        return DemographicErrorHandler(logger=logger)

    def path(self, **kwargs: Any) -> str:
        return "digital/demographic"

    def stream_slices(
        self,
        sync_mode: SyncMode,
        cursor_field: Optional[List[str]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Optional[Mapping[str, Any]]]:
        cutoff = (self._today() - timedelta(days=self._lookback_days)).strftime(DATE_FMT)
        probe = DigitalItems(
            authenticator=self.authenticator,
            cod_client=self._cod_client,
            page_size=self.page_size,
            start_date=max(self._configured_start_date, cutoff),
            end_date=self._configured_end_date,
            lookback_window_days=0,
        )
        rows: List[Mapping[str, Any]] = []
        for sl in probe.stream_slices(sync_mode=SyncMode.full_refresh):
            rows.extend(probe.read_records(sync_mode=SyncMode.full_refresh, stream_slice=sl))
        candidates = select_demographic_candidates(rows, cutoff)
        logger.info("digital_demographic: %d candidate campaigns (cutoff=%s)", len(candidates), cutoff)
        for cod, name in candidates:
            yield {"codCampaign": cod, "campaign": name}

    def request_body_json(
        self,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        stream_slice = stream_slice or {}
        return {
            "codClient": self._cod_client,
            "campaigns": [stream_slice["campaign"]],
        }

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> Iterable[Mapping[str, Any]]:
        if response.status_code == 504:
            return
        payload = response.json()
        entries = payload if isinstance(payload, list) else payload.get("content") or []
        for entry in entries:
            yield from explode_demographic(entry)
