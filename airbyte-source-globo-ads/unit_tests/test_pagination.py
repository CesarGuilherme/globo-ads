import json
from urllib.parse import urljoin

import requests

from source_globo_ads.auth import BareTokenAuthenticator
from source_globo_ads.streams.demographic import DigitalDemographic
from source_globo_ads.streams.items import DigitalItems


def _response(body: dict, sent_page: int) -> requests.Response:
    resp = requests.Response()
    resp.status_code = 200
    resp._content = json.dumps(body).encode()
    resp.encoding = "utf-8"
    resp.url = "https://api-ads-resultados.mybackstage.globo.com/api/v1/digital/items"
    req = requests.Request(
        "POST",
        resp.url,
        json={"page": sent_page, "size": 2, "startDate": "2026-05-01", "endDate": "2026-05-01"},
    )
    resp.request = req.prepare()
    # requests.Request.json sets body as bytes via prepare(); force the JSON we sent.
    resp.request.body = json.dumps({"page": sent_page, "size": 2})
    return resp


def build():
    return DigitalItems(
        authenticator=BareTokenAuthenticator("tok"),
        cod_client=258469,
        page_size=2,
        start_date="2026-05-01",
        end_date="2026-05-01",
    )


def test_next_page_token_advances_while_not_last():
    stream = build()
    resp = _response(
        {"content": [{"date": "2026-05-01"}], "last": False, "totalPages": 3, "number": 0},
        sent_page=0,
    )
    assert stream.next_page_token(resp) == {"page": 1}


def test_next_page_token_stops_on_last_flag():
    stream = build()
    resp = _response(
        {"content": [{"date": "2026-05-01"}], "last": True, "totalPages": 1, "number": 0},
        sent_page=0,
    )
    assert stream.next_page_token(resp) is None


def test_urljoin_keeps_api_v1_prefix():
    """HttpStream uses urllib urljoin; a leading slash on path drops /api/v1."""
    stream = build()
    assert urljoin(stream.url_base, stream.path()) == (
        "https://api-ads-resultados.mybackstage.globo.com/api/v1/digital/items"
    )
    demo = DigitalDemographic(
        authenticator=BareTokenAuthenticator("tok"),
        cod_client=258469,
    )
    assert urljoin(demo.url_base, demo.path()) == (
        "https://api-ads-resultados.mybackstage.globo.com/api/v1/digital/demographic"
    )


def test_next_page_token_stops_on_empty_content():
    stream = build()
    resp = _response({"content": [], "last": False, "totalPages": 2, "number": 0}, sent_page=0)
    assert stream.next_page_token(resp) is None
