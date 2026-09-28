"""
currency_models.py
===================
"Do NOT treat every currency identically." This module builds each asset's
effective category-weight profile from the DEFAULT_BASE_WEIGHTS /
XAU_WEIGHTS in config.py, zeroing out categories that do not apply to that
asset (Commodities, China Exposure, Safe-Haven -- see
CATEGORY_ASSET_RESTRICTIONS) and renormalizing the rest back to 100%.

It also documents, per the brief's "Special Currency Models" section, which
extra drivers/metrics matter most for each currency -- this is informational
(surfaced in the UI) since the actual mechanics live in metric_catalog.py.
"""

from copy import deepcopy
from typing import Dict

from config import (
    ALL_ASSETS, CURRENCIES, CATEGORIES, CATEGORY_ASSET_RESTRICTIONS,
    DEFAULT_BASE_WEIGHTS, XAU_WEIGHTS, DEFAULT_RISK_BETA,
)


def build_default_weight_profiles() -> Dict[str, Dict[str, float]]:
    """One category-weight dict per asset, each summing to 100."""
    profiles = {}
    for asset in CURRENCIES:
        profiles[asset] = _renormalized_profile(asset, DEFAULT_BASE_WEIGHTS)
    profiles["XAU"] = _renormalized_profile("XAU", XAU_WEIGHTS)
    return profiles


def _renormalized_profile(asset: str, base_weights: Dict[str, float]) -> Dict[str, float]:
    weights = deepcopy(base_weights)
    for cat_key, allowed_assets in CATEGORY_ASSET_RESTRICTIONS.items():
        if asset not in allowed_assets:
            weights[cat_key] = 0
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: (v / total) * 100.0 for k, v in weights.items()}


def build_default_risk_beta() -> Dict[str, float]:
    return deepcopy(DEFAULT_RISK_BETA)


# ---------------------------------------------------------------------------
# Informational: which extra factors matter most per currency (Section
# "Special Currency Models" of the brief). Shown on the currency detail page.
# ---------------------------------------------------------------------------

SPECIAL_MODEL_NOTES = {
    "USD": "Fed policy path, US Treasury yields, US CPI/labor prints, global reserve/safe-haven role, "
           "global USD liquidity conditions.",
    "EUR": "ECB policy path, Eurozone (esp. German) yields and inflation, growth divergence across the bloc, "
           "energy-price exposure.",
    "GBP": "BoE policy path, UK inflation and wage growth, gilt yields, UK growth momentum.",
    "JPY": "BoJ policy and yield-curve settings, Japanese wage growth (key for BoJ normalization), global "
           "risk sentiment and safe-haven flows.",
    "CHF": "SNB policy and FX considerations, Swiss inflation, safe-haven demand in stress periods.",
    "CAD": "BoC policy path, oil prices (WTI/Brent), Canadian labor data, US-Canada rate differential.",
    "AUD": "RBA policy path, iron ore and broader commodity prices, Chinese growth/PMI, global risk appetite.",
    "NZD": "RBNZ policy path, dairy prices (Global Dairy Trade auctions), Chinese growth, global risk appetite.",
    "XAU": "US real yields, Fed policy expectations (via USD), global risk sentiment, ETF flows, central-bank "
           "gold demand, and geopolitical stress. XAU uses its own weighting profile, not a currency template.",
}
