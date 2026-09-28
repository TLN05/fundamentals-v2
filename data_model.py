"""
data_model.py
=============
Standardized internal schema for the whole engine.

Every metric -- whatever asset, category, or eventual data source it comes
from -- is represented as a RawValue with this exact shape:

    value, previous_value, forecast, date, source, frequency, notes

This is deliberate: it is the contract between the data-provider layer
(data_providers/) and everything downstream (scoring_engine.py,
normalization, the UI). A future API-backed provider only needs to produce
RawValue objects keyed the same way ManualDataProvider does; nothing in
scoring_engine.py, currency_models.py, or components/ needs to change.
"""

from dataclasses import dataclass, field
from datetime import date as date_type, datetime
from typing import Any, Dict, List, Optional

from config import (
    FRESHNESS_FRESH,
    FRESHNESS_AGING,
    FRESHNESS_STALE,
    FRESHNESS_MISSING,
    FRESHNESS_THRESHOLDS_DAYS,
)


# ---------------------------------------------------------------------------
# Raw field definitions (what the input form collects / what a future API
# provider must supply)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawFieldDef:
    key: str                     # unique key, e.g. "cpi_yoy"
    label: str                   # human label, e.g. "CPI YoY"
    category: str                # category code, e.g. "INF"
    field_type: str              # "number" | "percent" | "categorical"
    unit: str = ""                # "%", "index pts", "" etc.
    options: Optional[List[str]] = None    # for categorical fields
    frequency: str = "Monthly"   # default reporting frequency (user can override)
    assets: Optional[List[str]] = None     # None = all assets
    tooltip: str = ""
    has_previous: bool = True
    has_forecast: bool = False
    computed: bool = False       # True = derived automatically (e.g. XAU's USD proxy),
                                  # never shown on a manual input form


# ---------------------------------------------------------------------------
# A single stored value for one (asset, raw field) pair
# ---------------------------------------------------------------------------

@dataclass
class RawValue:
    value: Optional[Any] = None
    previous_value: Optional[Any] = None
    forecast: Optional[Any] = None
    date: Optional[str] = None          # ISO date string "YYYY-MM-DD"
    source: Optional[str] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None

    def is_populated(self) -> bool:
        return self.value is not None

    def freshness(self, as_of: Optional[date_type] = None) -> str:
        if not self.is_populated():
            return FRESHNESS_MISSING
        if not self.date:
            return FRESHNESS_AGING  # populated but undated -> can't trust it fully
        try:
            d = datetime.strptime(self.date, "%Y-%m-%d").date()
        except ValueError:
            return FRESHNESS_AGING
        as_of = as_of or date_type.today()
        age_days = (as_of - d).days
        freq = self.frequency or "Monthly"
        fresh_max, aging_max = FRESHNESS_THRESHOLDS_DAYS.get(freq, FRESHNESS_THRESHOLDS_DAYS["Irregular"])
        if age_days < 0:
            return FRESHNESS_AGING  # dated in the future -- treat cautiously
        if age_days <= fresh_max:
            return FRESHNESS_FRESH
        if age_days <= aging_max:
            return FRESHNESS_AGING
        return FRESHNESS_STALE


# ---------------------------------------------------------------------------
# Driver definitions (a "driver" is one scored, explainable component built
# from one or more raw fields; drivers roll up into categories)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DriverDef:
    key: str
    label: str
    category: str
    eval_type: str                # see scoring_engine.EVALUATORS
    params: Dict[str, Any] = field(default_factory=dict)
    weight_in_category: float = 1.0   # relative weight among drivers in the same category (renormalized)
    assets: Optional[List[str]] = None
    tooltip: str = ""


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class DriverScore:
    key: str
    label: str
    category: str
    score: Optional[float]           # -100..100, or None if unavailable
    weight_in_category: float        # 0..1, renormalized among available drivers
    explanation: str
    raw: Dict[str, RawValue] = field(default_factory=dict)
    available: bool = True
    freshness: str = FRESHNESS_FRESH
    data_date: Optional[str] = None
    crowding_flag: bool = False


@dataclass
class CategoryScore:
    key: str
    label: str
    score: Optional[float]           # -100..100, or None if fully unavailable
    weight: float                    # 0..100, renormalized asset-level category weight actually used
    base_weight: float               # 0..100, the configured weight before renormalization
    contribution: float              # weight/100 * score
    drivers: List[DriverScore]
    coverage: float                  # 0..1, fraction of this category's driver weight backed by data
    available: bool


@dataclass
class AssetScore:
    asset: str
    horizon: str
    final_score: float               # -100..100
    bias: str
    confidence: float                # 0..100
    alignment: float                 # 0..100 (Fundamental Alignment Score)
    data_coverage: float             # 0..100, overall % of weight backed by available data
    categories: List[CategoryScore]
    top_bullish: List[DriverScore]
    top_bearish: List[DriverScore]
    conflict_note: Optional[str]
    as_of: str
