from airbyte_cdk.sources.streams.http.requests_native_auth import TokenAuthenticator


class BareTokenAuthenticator(TokenAuthenticator):
    """Globo Ads wants the raw platform token in Authorization, not 'Bearer <token>'."""

    def __init__(self, token: str):
        super().__init__(token=token, auth_method="")

    @property
    def token(self) -> str:
        return self._token
