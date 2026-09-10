from source_globo_ads.auth import BareTokenAuthenticator


def test_auth_header_is_bare_token_without_bearer():
    auth = BareTokenAuthenticator("08da2cc3-plain-token")
    assert auth.get_auth_header() == {"Authorization": "08da2cc3-plain-token"}
    assert "Bearer" not in auth.get_auth_header()["Authorization"]
