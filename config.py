"""
config.py
=========
Single source of truth for everything that is a *choice* rather than a
*calculation*: which assets exist, which categories exist, default category
weights per asset, horizon adjustments, and bias/label thresholds.

Nothing in scoring_engine.py hard-codes a weight or a threshold -- it all
flows from here, so the model stays transparent and editable from the
"Model Settings" screen (which mutates copies of these structures held in
st.session_state, never these module-level defaults directly).
"""

from copy import deepcopy

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
ALL_ASSETS = CURRENCIES + ["XAU"]

ASSET_NAMES = {
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CHF": "Swiss Franc",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "NZD": "New Zealand Dollar",
    "XAU": "Gold",
}

CENTRAL_BANKS = {
    "USD": "Federal Reserve (Fed)",
    "EUR": "European Central Bank (ECB)",
    "GBP": "Bank of England (BoE)",
    "JPY": "Bank of Japan (BoJ)",
    "CHF": "Swiss National Bank (SNB)",
    "CAD": "Bank of Canada (BoC)",
    "AUD": "Reserve Bank of Australia (RBA)",
    "NZD": "Reserve Bank of New Zealand (RBNZ)",
    "XAU": "N/A (Fed-driven via USD/real yields)",
}

# ---------------------------------------------------------------------------
# Categories (the 19 top-level fundamental categories)
# ---------------------------------------------------------------------------

CATEGORIES = {
    "MP":   "Monetary Policy & Rate Expectations",
    "YD":   "Yield Differential",
    "INF":  "Inflation",
    "LAB":  "Labor Market",
    "GRW":  "Growth",
    "MOM":  "Economic Momentum",
    "TRD":  "Trade / Current Account",
    "CMD":  "Commodities",
    "CHN":  "China Exposure",
    "RISK": "Global Risk Sentiment",
    "SAFE": "Safe-Haven Factors",
    "COT":  "CFTC Positioning",
    "RY":   "Real Yields",
    "VAL":  "Valuation (REER)",
    "FIS":  "Fiscal Conditions",
    "CBS":  "Central Bank Balance Sheet",
    "SURP": "Economic Surprises",
    "EXP":  "Expectation Changes",
    "GEO":  "Geopolitical / Economic Risk",
}

CATEGORY_ORDER = list(CATEGORIES.keys())

# Which categories only apply to a subset of assets. Assets not listed here
# get a weight of 0 for that category, and the remaining categories are
# renormalized so the profile still sums to 100 (see currency_models.py).
CATEGORY_ASSET_RESTRICTIONS = {
    "CMD": ["AUD", "CAD", "NZD"],
    "CHN": ["AUD", "NZD", "CAD"],
    "SAFE": ["USD", "JPY", "CHF", "XAU"],
}

# ---------------------------------------------------------------------------
# Default category weights (%), BEFORE asset-restriction renormalization.
# These represent a "generic" G10 currency. AUD/CAD/NZD/XAU profiles are
# derived from this base with adjustments in currency_models.py. Must sum to
# 100 -- validated on import and again whenever Model Settings saves changes.
# ---------------------------------------------------------------------------

DEFAULT_BASE_WEIGHTS = {
    "MP":   15,
    "YD":   11,
    "INF":  7,
    "LAB":  6,
    "GRW":  6,
    "MOM":  6,
    "TRD":  4,
    "CMD":  5,
    "CHN":  3,
    "RISK": 6,
    "SAFE": 4,
    "COT":  5,
    "RY":   5,
    "VAL":  3,
    "FIS":  3,
    "CBS":  4,
    "SURP": 3,
    "EXP":  3,
    "GEO":  1,
}
assert sum(DEFAULT_BASE_WEIGHTS.values()) == 100, "Base weights must sum to 100"

# Gold gets an entirely separate weighting profile (Section 15 of the brief):
# growth/labor/trade/momentum/fiscal/commodities/china are not meaningful
# drivers of gold, so those categories are zeroed and weight is concentrated
# in real yields, the USD/Fed proxy, risk, safe-haven/ETF/CB-demand,
# inflation expectations, liquidity, positioning and geopolitics.
XAU_WEIGHTS = {
    "MP":   18,  # Fed policy path, proxied via computed USD score
    "YD":   0,
    "INF":  10,  # inflation expectations, not realized CPI
    "LAB":  0,
    "GRW":  0,
    "MOM":  0,
    "TRD":  0,
    "CMD":  0,
    "CHN":  0,
    "RISK": 12,
    "SAFE": 16,  # ETF flows, CB gold demand, geopolitical/safe-haven demand
    "COT":  8,
    "RY":   20,
    "VAL":  0,
    "FIS":  0,
    "CBS":  10,  # global liquidity / major CB balance sheets
    "SURP": 0,
    "EXP":  0,
    "GEO":  6,
}
assert sum(XAU_WEIGHTS.values()) == 100, "XAU weights must sum to 100"

# ---------------------------------------------------------------------------
# Horizon adjustments -- multipliers applied to category weights before
# renormalization, per time horizon. Only categories explicitly called out
# in the brief as horizon-sensitive are adjusted; everything else is neutral
# (1.0) across horizons. Monetary policy is intentionally left at 1.0 across
# the board since the brief says it "can matter across all horizons".
# ---------------------------------------------------------------------------

HORIZONS = ["Short-Term (1-4w)", "Medium-Term (1-3m)", "Long-Term (3-12m)"]

HORIZON_MULTIPLIERS = {
    "Short-Term (1-4w)": {
        "COT": 1.5, "SURP": 1.4, "EXP": 1.2, "MOM": 1.2,
        "VAL": 0.4, "FIS": 0.3, "GRW": 0.7,
    },
    "Medium-Term (1-3m)": {
        "COT": 0.8, "SURP": 0.9, "EXP": 1.1, "MOM": 1.0,
        "VAL": 0.8, "FIS": 0.7, "GRW": 1.0,
    },
    "Long-Term (3-12m)": {
        "COT": 0.3, "SURP": 0.3, "EXP": 0.7, "MOM": 0.7,
        "VAL": 1.5, "FIS": 1.4, "GRW": 1.2,
    },
}

DEFAULT_HORIZON = "Medium-Term (1-3m)"

# ---------------------------------------------------------------------------
# Bias / freshness / risk-beta labels
# ---------------------------------------------------------------------------

BIAS_BANDS = [
    (75, 100, "Very Bullish"),
    (50, 75, "Bullish"),
    (25, 50, "Moderately Bullish"),
    (-24, 25, "Neutral"),
    (-49, -24, "Moderately Bearish"),
    (-74, -49, "Bearish"),
    (-100, -74, "Very Bearish"),
]


def score_to_bias(score: float) -> str:
    for lo, hi, label in BIAS_BANDS:
        if lo <= score <= hi:
            return label
    return "Neutral"


FRESHNESS_FRESH = "Fresh"
FRESHNESS_AGING = "Aging"
FRESHNESS_STALE = "Stale"
FRESHNESS_MISSING = "Unavailable"

# max age in days, by reporting frequency, before a value becomes Aging /
# Stale
FRESHNESS_THRESHOLDS_DAYS = {
    "Daily":     (3, 10),
    "Weekly":    (10, 25),
    "Monthly":   (35, 70),
    "Quarterly": (100, 200),
    "Irregular": (30, 90),
}

# Risk-sentiment beta: how each asset typically responds to a Risk-On
# reading (positive beta) vs Risk-Off (safe-haven, negative beta).
# Applied to the RISK category driver. Editable in Model Settings.
DEFAULT_RISK_BETA = {
    "USD": -0.3,
    "EUR": 0.6,
    "GBP": 0.5,
    "JPY": -0.9,
    "CHF": -0.8,
    "CAD": 0.7,
    "AUD": 1.0,
    "NZD": 1.0,
    "XAU": 0.3,
}

ALIGNMENT_NEUTRAL_BAND = 24  # a category score within +/-24 counts as neutral, not a
                              # vote for or against the final direction, when computing
                              # the Fundamental Alignment score.

ALIGNMENT_MIXED_THRESHOLD = 60  # below this alignment %, label as "Mixed fundamental environment"


def default_weights_for_profile(base: dict) -> dict:
    return deepcopy(base)
