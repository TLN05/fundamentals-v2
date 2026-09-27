"""
data_providers/base.py
=======================
The ONLY contract the scoring engine relies on. scoring_engine.py never
imports Streamlit, never imports ManualDataProvider by name in its scoring
logic, and never reads a dict directly -- it only calls DataProvider methods.

To plug in a real market-data / macro-data API later:
  1. Subclass DataProvider.
  2. Implement get(asset, field_key) -> RawValue (or None if unavailable).
  3. Implement set(...) if the provider is writable (an API provider
     typically won't be -- it can raise NotImplementedError).
  4. Pass an instance of your new provider into scoring_engine.compute_all()
     wherever ManualDataProvider is passed today.

No changes are required in scoring_engine.py, normalization.py,
currency_models.py, or any component under components/.
"""

from abc import ABC, abstractmethod
from typing import Optional

from data_model import RawValue


class DataProvider(ABC):
    """Abstract source of RawValue objects, keyed by (asset, field_key)."""

    @abstractmethod
    def get(self, asset: str, field_key: str) -> Optional[RawValue]:
        """Return the RawValue for this asset/field, or None if there is no
        data at all (not even a partially-populated record)."""
        raise NotImplementedError

    def get_or_empty(self, asset: str, field_key: str) -> RawValue:
        val = self.get(asset, field_key)
        return val if val is not None else RawValue()

    @abstractmethod
    def set(self, asset: str, field_key: str, raw_value: RawValue) -> None:
        """Store/overwrite a RawValue. Manual providers implement this fully;
        a read-only API provider may raise NotImplementedError."""
        raise NotImplementedError

    @abstractmethod
    def coverage_report(self, asset: str, field_keys) -> float:
        """Return the fraction (0..1) of the given field_keys that are
        populated for this asset. Used for the 'Data coverage: NN%' display."""
        raise NotImplementedError
