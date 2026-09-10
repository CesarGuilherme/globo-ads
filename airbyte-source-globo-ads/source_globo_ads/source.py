import logging
from typing import Any, List, Mapping, Optional, Tuple

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream

from .auth import BareTokenAuthenticator
from .streams.base import DEFAULT_PAGE_SIZE, DEFAULT_WINDOW_IN_DAYS
from .streams.demographic import DEFAULT_DEMOGRAPHIC_LOOKBACK_DAYS, DigitalDemographic
from .streams.items import DigitalItems


class SourceGloboAds(AbstractSource):
    def _authenticator(self, config: Mapping[str, Any]) -> BareTokenAuthenticator:
        return BareTokenAuthenticator(config["api_token"])

    def _items(self, config: Mapping[str, Any], **overrides: Any) -> DigitalItems:
        kwargs: Mapping[str, Any] = {
            "authenticator": self._authenticator(config),
            "cod_client": int(config["cod_client"]),
            "start_date": config.get("start_date"),
            "end_date": config.get("end_date"),
            "lookback_window_days": config.get("lookback_window_days", 7),
            "window_in_days": config.get("window_in_days", DEFAULT_WINDOW_IN_DAYS),
            "page_size": config.get("page_size", DEFAULT_PAGE_SIZE),
        }
        kwargs.update(overrides)
        return DigitalItems(**kwargs)

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[Any]]:
        try:
            probe = self._items(config, lookback_window_days=0)
            slices = list(probe.stream_slices(sync_mode=SyncMode.full_refresh))
            if not slices:
                return True, None
            next(iter(probe.read_records(sync_mode=SyncMode.full_refresh, stream_slice=slices[-1])), None)
        except Exception as e:
            logger.error(f"Globo Ads check_connection failed: {e}")
            return False, str(e)
        return True, None

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        items = self._items(config)
        demographic = DigitalDemographic(
            items=items,
            authenticator=self._authenticator(config),
            cod_client=int(config["cod_client"]),
            page_size=config.get("page_size", DEFAULT_PAGE_SIZE),
            start_date=config.get("start_date"),
            end_date=config.get("end_date"),
            demographic_lookback_days=config.get(
                "demographic_lookback_days", DEFAULT_DEMOGRAPHIC_LOOKBACK_DAYS
            ),
        )
        return [items, demographic]
