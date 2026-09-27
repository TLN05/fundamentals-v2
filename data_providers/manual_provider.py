"""
data_providers/manual_provider.py
==================================
Version-1 data source: everything is typed in by the user through
components/input_forms.py and held in memory (backed by Streamlit's
session_state so it survives reruns within a session).

This class knows NOTHING about scoring, weights, or categories -- it is a
pure key/value store keyed by (asset, field_key), storing RawValue objects.
That separation is what lets a future API provider be a drop-in replacement.
"""

from typing import Dict, Optional, Tuple

from data_model import RawValue
from data_providers.base import DataProvider


class ManualDataProvider(DataProvider):
    def __init__(self, initial: Optional[Dict[Tuple[str, str], RawValue]] = None):
        self._store: Dict[Tuple[str, str], RawValue] = dict(initial or {})

    def get(self, asset: str, field_key: str) -> Optional[RawValue]:
        return self._store.get((asset, field_key))

    def set(self, asset: str, field_key: str, raw_value: RawValue) -> None:
        self._store[(asset, field_key)] = raw_value

    def coverage_report(self, asset: str, field_keys) -> float:
        field_keys = list(field_keys)
        if not field_keys:
            return 1.0
        populated = 0
        for fk in field_keys:
            rv = self.get(asset, fk)
            if rv is not None and rv.is_populated():
                populated += 1
        return populated / len(field_keys)

    # convenience helpers used by the input-forms UI --------------------
    def all_for_asset(self, asset: str) -> Dict[str, RawValue]:
        return {fk: rv for (a, fk), rv in self._store.items() if a == asset}

    def export_dict(self) -> dict:
        """Serialize to plain dict (for session_state / JSON export)."""
        return {
            f"{a}||{fk}": vars(rv) for (a, fk), rv in self._store.items()
        }

    @classmethod
    def from_export_dict(cls, data: dict) -> "ManualDataProvider":
        store = {}
        for key, rv_dict in (data or {}).items():
            a, fk = key.split("||", 1)
            store[(a, fk)] = RawValue(**rv_dict)
        return cls(store)
