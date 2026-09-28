"""
Persistent manual data provider backed by the Supabase Data REST API.

The secret key is used only by the Streamlit server. Keep this app private
unless it is protected by an application-level sign-in.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_model import RawValue
from data_providers.manual_provider import ManualDataProvider


class SupabaseDataProvider(ManualDataProvider):
    """ManualDataProvider whose snapshot is loaded from and saved to Supabase."""

    TABLE = "manual_values"
    PAGE_SIZE = 1000
    BATCH_SIZE = 500

    def __init__(self, project_url: str, api_key: str):
        super().__init__()
        self._project_url = project_url.rstrip("/")
        self._api_key = api_key
        self._load()

    def _request(self, method: str, query: str = "", payload=None):
        url = f"{self._project_url}/rest/v1/{self.TABLE}"
        if query:
            url = f"{url}?{query}"

        headers = {
            "apikey": self._api_key,
            "Accept": "application/json",
        }
        # New Supabase secret keys are API keys, not JWT bearer tokens.
        # Legacy service_role keys are JWTs and also need Authorization.
        if not self._api_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if method == "POST":
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Supabase returned HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach Supabase: {exc.reason}") from exc

        if not response_body:
            return None
        return json.loads(response_body.decode("utf-8"))

    def _load(self):
        offset = 0
        while True:
            query = urlencode({
                "select": "asset,field_key,raw_value",
                "limit": self.PAGE_SIZE,
                "offset": offset,
            })
            rows = self._request("GET", query=query) or []
            for row in rows:
                self._store[(row["asset"], row["field_key"])] = RawValue(
                    **(row.get("raw_value") or {})
                )
            if len(rows) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE

    def save(self):
        """Upsert the current in-memory snapshot in bounded API batches."""
        rows = [
            {
                "asset": asset,
                "field_key": field_key,
                "raw_value": vars(raw_value),
            }
            for (asset, field_key), raw_value in self._store.items()
        ]
        for start in range(0, len(rows), self.BATCH_SIZE):
            batch = rows[start:start + self.BATCH_SIZE]
            self._request(
                "POST",
                query=urlencode({"on_conflict": "asset,field_key"}),
                payload=batch,
            )

    def clear(self):
        """Delete all stored manual inputs and clear this provider."""
        self._request("DELETE", query="asset=not.is.null")
        self._store.clear()
