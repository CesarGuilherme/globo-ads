import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

from airbyte_cdk.sources.streams.http import HttpStream

logger = logging.getLogger("airbyte")

# Trailing slash is required: urllib.urljoin drops the last path segment of a
# prefix without it when `path` is absolute (`/digital/items` → host/digital/items).
API_BASE = "https://api-ads-resultados.mybackstage.globo.com/api/v1/"
DATE_FMT = "%Y-%m-%d"
SP_TZ = ZoneInfo("America/Sao_Paulo")
DEFAULT_START_DATE = "2023-01-01"
DEFAULT_WINDOW_IN_DAYS = 31
DEFAULT_PAGE_SIZE = 1000


def flatten(rec: Mapping[str, Any]) -> dict:
    """Dot-to-underscore flatten of one-level nested impression/video/investment objects."""
    out: dict = {}
    for k, v in rec.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                out[f"{k}_{kk}"] = vv
        else:
            out[k] = v
    return out


def _parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


class GloboAdsStream(HttpStream):
    url_base = API_BASE
    http_method = "POST"
    primary_key = None

    def __init__(
        self,
        *,
        cod_client: int,
        page_size: int = DEFAULT_PAGE_SIZE,
        authenticator: Optional[Any] = None,
        **kwargs: Any,
    ):
        # CDK 7 HttpStream keeps the authenticator on HttpClient only — it never
        # sets self.authenticator. Demographic needs a copy to probe /digital/items.
        self._authenticator = authenticator
        super().__init__(authenticator=authenticator, **kwargs)
        self._cod_client = cod_client
        self.page_size = page_size

    def _today(self) -> date:
        return datetime.now(SP_TZ).date()

    def get_json_schema(self) -> Mapping[str, Any]:
        path = Path(__file__).parent.parent / "schemas" / f"{self.name}.json"
        return json.loads(path.read_text())
