"""
Persistent manual data provider backed by the Supabase Data REST API.

The secret key is used only by the Streamlit server. Keep the app private or
behind the APP_PASSWORD gate (see app.py).

Changes vs. PR #1: saves only rows that changed since the last load/save
(instead of re-uploading every row on every Streamlit rerun), tolerates
unknown keys in stored JSON, and never touches scoring code.
"""

import json
from dataclasses import fields as dc_fields
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_model import RawValue
from data_providers.manual_provider import ManualDataProvider

_RAW_KEYS = {f.name for f in dc_fields(RawValue)}


def _serialize(raw_value: RawValue) -> str:
    return json.dumps(vars(raw_value), sort_keys=True, ensure_ascii=False, default=str)


class SupabaseDataProvider(ManualDataProvider):
    """ManualDataProvider whose snapshot is loaded from and saved to Supabase."""

    TABLE = "manual_values"
    PAGE_SIZE = 1000
    BATCH_SIZE = 500

    def __init__(self, project_url: str, api_key: str):
        super().__init__()
        self._project_url = project_url.rstrip("/")
        self._api_key = api_key
        self._saved = {}  # (asset, field_key) -> serialized JSON last known in Supabase
        self._load()

    def _request(self, method: str, query: str = "", payload=None):
        url = f"{self._project_url}/rest/v1/{self.TABLE}"
        if query:
            url = f"{url}?{query}"
        headers = {"apikey": self._api_key, "Accept": "application/json"}
        # New sb_secret_ keys are API keys, not JWTs; legacy service_role keys are JWTs.
        if not self._api_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            if method == "POST":
                headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase returned HTTP {exc.code}: {detail[:500]}") from exc
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
                "order": "asset,field_key",   # stable paging
                "limit": self.PAGE_SIZE,
                "offset": offset,
            })
            rows = self._request("GET", query=query) or []
            for row in rows:
                data = {k: v for k, v in (row.get("raw_value") or {}).items() if k in _RAW_KEYS}
                key = (row["asset"], row["field_key"])
                self._store[key] = RawValue(**data)
                self._saved[key] = _serialize(self._store[key])
            if len(rows) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE

    def save(self):
        """Upsert only the rows changed since the last load/save."""
        changed = []
        for key, raw_value in self._store.items():
            ser = _serialize(raw_value)
            if self._saved.get(key) != ser:
                changed.append((key, ser, raw_value))
        for start in range(0, len(changed), self.BATCH_SIZE):
            batch = changed[start:start + self.BATCH_SIZE]
            self._request(
                "POST",
                query=urlencode({"on_conflict": "asset,field_key"}),
                payload=[{"asset": k[0], "field_key": k[1], "raw_value": vars(rv)} for k, _, rv in batch],
            )
            for k, ser, _ in batch:   # mark saved only after the batch succeeded
                self._saved[k] = ser

    def clear(self):
        """Delete all stored manual inputs and clear this provider."""
        self._request("DELETE", query="asset=not.is.null")
        self._store.clear()
        self._saved.clear()
