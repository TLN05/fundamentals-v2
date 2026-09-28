"""
metric_catalog.py
==================
The complete list of (1) raw fields collected per asset, grouped by category,
and (2) the scored "drivers" built from those raw fields.

This is DATA, not logic -- scoring_engine.py's small set of generic
evaluators (see EVALUATORS there) interprets these definitions. Adding a new
metric or driver means adding an entry here; it does not require touching
the scoring engine, the UI, or the weighting system.

Design choices that prevent double-counting (see also README):
  - Absolute policy-rate LEVEL is never scored directly -- only the
    forward-looking trajectory (Section 1) and, separately, the outright
    yield LEVEL/TREND (Section 3, a distinct concept: term structure, not
    central-bank intent).
  - Rate-EXPECTATION REVISIONS (the "priced path changed") live only in the
    Expectation Changes (EXP) category, not duplicated in Monetary Policy.
  - CPI, core CPI-vs-target and wage growth are combined into one
    inflation-reaction driver instead of being scored independently and
    summed, since they move together.
  - Central-bank divergence (Section 21) is deliberately NOT a standalone
    category: it is inherently a pairwise concept, so it is computed at the
    pair level in components/matrix.py (difference of two assets' MP+YD
    scores) rather than scored a second time per-asset.
"""

from config import CURRENCIES, ALL_ASSETS
from data_model import RawFieldDef, DriverDef

# ---------------------------------------------------------------------------
# Categorical value -> score mappings (shared, editable in one place)
# ---------------------------------------------------------------------------

STANCE_MAPPING = {"Very Dovish": -100, "Dovish": -50, "Neutral": 0, "Hawkish": 50, "Very Hawkish": 100}
GUIDANCE_MAPPING = {"Dovish": -60, "Balanced": 0, "Hawkish": 60}
TREND_MAPPING = {"Improving": 50, "Stable": 0, "Worsening": -50}
CHINA_TRAJECTORY_MAPPING = {"Strong": 80, "Improving": 40, "Neutral": 0, "Weakening": -40, "Weak": -80}
RISK_ENV_MAPPING = {"Strong Risk-On": 80, "Moderate Risk-On": 40, "Neutral": 0,
                     "Moderate Risk-Off": -40, "Strong Risk-Off": -80}
SAFE_HAVEN_DEMAND_MAPPING = {"Strong": 70, "Moderate": 35, "Weak": 0, "None": -30}
GEOPOLITICAL_STRESS_MAPPING = {"Low": -20, "Medium": 20, "High": 60}
ETF_FLOWS_MAPPING = {"Inflows": 50, "Neutral": 0, "Outflows": -50}
CB_GOLD_DEMAND_MAPPING = {"Strong": 50, "Moderate": 20, "Weak": -20}
CBS_TREND_MAPPING_FX = {"Expanding": -60, "Neutral": 0, "Contracting": 60}
GLOBAL_LIQUIDITY_MAPPING_XAU = {"Expanding": 50, "Neutral": 0, "Contracting": -50}
FISCAL_TREND_MAPPING = {"Tightening": 30, "Neutral": 0, "Expansionary": -30}
GEO_IMPACT_MAPPING = {"Positive": 50, "Neutral": 0, "Negative": -50}
CONFIDENCE_RELEVANCE_MAPPING = {"Low": 0.4, "Medium": 0.7, "High": 1.0}
SURPRISE_MAPPING = {"Beat": 60, "In-line": 0, "Miss": -60}
SURPRISE_RELEVANCE_MAPPING = {"Low": 0.3, "Medium": 0.6, "High": 1.0}

# ---------------------------------------------------------------------------
# RAW FIELDS
# ---------------------------------------------------------------------------

RAW_FIELDS = [
    # ---- Monetary Policy (MP) ------------------------------------------------
    RawFieldDef("current_policy_rate", "Current Policy Rate", "MP", "percent", "%",
                frequency="Irregular", assets=CURRENCIES,
                tooltip="The central bank's current benchmark rate."),
    RawFieldDef("expected_rate_3m", "Expected Policy Rate (3M)", "MP", "percent", "%",
                frequency="Irregular", assets=CURRENCIES,
                tooltip="Market-implied policy rate 3 months forward (OIS/futures-implied)."),
    RawFieldDef("expected_rate_6m", "Expected Policy Rate (6M)", "MP", "percent", "%",
                frequency="Irregular", assets=CURRENCIES, tooltip="Market-implied policy rate 6 months forward."),
    RawFieldDef("expected_rate_12m", "Expected Policy Rate (12M)", "MP", "percent", "%",
                frequency="Irregular", assets=CURRENCIES,
                tooltip="Market-implied policy rate 12 months forward. This -- not the current rate -- "
                        "is the primary monetary-policy input."),
    RawFieldDef("policy_stance", "Central Bank Policy Stance", "MP", "categorical",
                options=list(STANCE_MAPPING.keys()), frequency="Irregular", assets=CURRENCIES,
                tooltip="Your read of the current overall stance."),
    RawFieldDef("forward_guidance_tone", "Latest Forward Guidance Tone", "MP", "categorical",
                options=list(GUIDANCE_MAPPING.keys()), frequency="Irregular", assets=CURRENCIES,
                tooltip="Tone of the most recent statement/press conference."),

    # ---- Yield Differential (YD) ---------------------------------------------
    RawFieldDef("yield_2y", "2Y Government Yield", "YD", "percent", "%", frequency="Daily", assets=CURRENCIES),
    RawFieldDef("yield_10y", "10Y Government Yield", "YD", "percent", "%", frequency="Daily", assets=ALL_ASSETS,
                tooltip="For XAU, enter the US 10Y nominal yield -- it feeds gold's Real Yield driver."),

    # ---- Inflation (INF) -------------------------------------------------------
    RawFieldDef("cpi_yoy", "Headline CPI YoY", "INF", "percent", "%", frequency="Monthly", assets=CURRENCIES),
    RawFieldDef("inflation_target", "Central Bank Inflation Target", "INF", "percent", "%",
                frequency="Irregular", assets=CURRENCIES),
    RawFieldDef("wage_growth", "Wage Growth YoY", "INF", "percent", "%", frequency="Quarterly", assets=CURRENCIES),
    RawFieldDef("inflation_expectation_10y", "10Y Breakeven Inflation Expectation", "RY", "percent", "%",
                frequency="Daily", assets=ALL_ASSETS,
                tooltip="Market-implied long-run inflation expectations; used for real yields and, for gold, "
                        "as its own inflation-expectations driver."),

    # ---- Labor Market (LAB) ----------------------------------------------------
    RawFieldDef("unemployment_rate", "Unemployment Rate", "LAB", "percent", "%",
                frequency="Monthly", assets=CURRENCIES),
    RawFieldDef("employment_growth_yoy", "Employment Growth YoY", "LAB", "percent", "%",
                frequency="Monthly", assets=CURRENCIES),

    # ---- Growth (GRW) ------------------------------------------------------------
    RawFieldDef("gdp_yoy", "GDP Growth YoY", "GRW", "percent", "%", frequency="Quarterly", assets=CURRENCIES),
    RawFieldDef("retail_sales_yoy", "Retail Sales YoY", "GRW", "percent", "%",
                frequency="Monthly", assets=CURRENCIES),

    # ---- Economic Momentum (MOM) --------------------------------------------------
    RawFieldDef("manuf_pmi", "Manufacturing PMI", "MOM", "number", "index", frequency="Monthly", assets=CURRENCIES),
    RawFieldDef("services_pmi", "Services PMI", "MOM", "number", "index", frequency="Monthly", assets=CURRENCIES),
    RawFieldDef("consumer_confidence", "Consumer Confidence Index", "MOM", "number", "index",
                frequency="Monthly", assets=CURRENCIES),

    # ---- Trade / Current Account (TRD) -----------------------------------------------
    RawFieldDef("current_account_pct_gdp", "Current Account (% of GDP)", "TRD", "percent", "%",
                frequency="Quarterly", assets=CURRENCIES),
    RawFieldDef("trade_balance_trend", "Trade Balance Trend", "TRD", "categorical",
                options=list(TREND_MAPPING.keys()), frequency="Monthly", assets=CURRENCIES, has_previous=False),

    # ---- Commodities (CMD) -- AUD / CAD / NZD only -----------------------------------
    RawFieldDef("commodity_price_change_3m", "Key Commodity 3M Change", "CMD", "percent", "%",
                frequency="Daily", assets=["AUD", "CAD", "NZD"],
                tooltip="AUD: iron ore. CAD: WTI/Brent crude. NZD: Global Dairy Trade index.", has_previous=False),
    RawFieldDef("terms_of_trade_trend", "Terms of Trade Trend", "CMD", "categorical",
                options=list(TREND_MAPPING.keys()), frequency="Quarterly", assets=["AUD", "CAD", "NZD"],
                has_previous=False),

    # ---- China Exposure (CHN) -- AUD / NZD / CAD only --------------------------------
    RawFieldDef("china_pmi", "China Manufacturing PMI", "CHN", "number", "index",
                frequency="Monthly", assets=["AUD", "NZD", "CAD"]),
    RawFieldDef("china_trajectory", "China Macro Trajectory", "CHN", "categorical",
                options=list(CHINA_TRAJECTORY_MAPPING.keys()), frequency="Monthly",
                assets=["AUD", "NZD", "CAD"], has_previous=False),

    # ---- Global Risk Sentiment (RISK) ------------------------------------------------
    RawFieldDef("risk_environment", "Global Risk Environment", "RISK", "categorical",
                options=list(RISK_ENV_MAPPING.keys()), frequency="Daily", assets=ALL_ASSETS, has_previous=False),
    RawFieldDef("vix_level", "VIX (or equivalent vol index)", "RISK", "number", "index",
                frequency="Daily", assets=ALL_ASSETS),

    # ---- Safe-Haven Factors (SAFE) -- USD / JPY / CHF / XAU only ----------------------
    RawFieldDef("safe_haven_demand_signal", "Safe-Haven Demand Signal", "SAFE", "categorical",
                options=list(SAFE_HAVEN_DEMAND_MAPPING.keys()), frequency="Daily",
                assets=["USD", "JPY", "CHF", "XAU"], has_previous=False),
    RawFieldDef("geopolitical_stress_level", "Geopolitical Stress Level", "SAFE", "categorical",
                options=list(GEOPOLITICAL_STRESS_MAPPING.keys()), frequency="Daily",
                assets=["USD", "JPY", "CHF", "XAU"], has_previous=False),
    RawFieldDef("etf_flows_trend", "Gold ETF Flows Trend", "SAFE", "categorical",
                options=list(ETF_FLOWS_MAPPING.keys()), frequency="Weekly", assets=["XAU"], has_previous=False),
    RawFieldDef("cb_gold_demand_trend", "Central-Bank Gold Demand Trend", "SAFE", "categorical",
                options=list(CB_GOLD_DEMAND_MAPPING.keys()), frequency="Quarterly", assets=["XAU"],
                has_previous=False),

    # ---- CFTC Positioning (COT) -------------------------------------------------------
    RawFieldDef("net_position_pct_oi", "Net Speculative Position (% of Open Interest)", "COT", "percent", "%",
                frequency="Weekly", assets=ALL_ASSETS,
                tooltip="Managed-money/leveraged-fund net long (+) or short (-) as % of open interest."),
    RawFieldDef("position_percentile", "Positioning Percentile (0-100, vs 3Y range)", "COT", "number", "pct",
                frequency="Weekly", assets=ALL_ASSETS, has_previous=False,
                tooltip="Where current positioning sits vs its own 3-year range. Extremes flag crowding risk, "
                        "independent of direction."),
    RawFieldDef("position_change_4w", "Net Position 4-Week Change (pts of OI)", "COT", "number", "pts",
                frequency="Weekly", assets=ALL_ASSETS, has_previous=False),

    # ---- Valuation / REER (VAL) --------------------------------------------------------
    RawFieldDef("reer_deviation_pct", "REER Deviation from Long-Term Average", "VAL", "percent", "%",
                frequency="Monthly", assets=CURRENCIES, has_previous=False,
                tooltip="BIS-style real effective exchange rate, % deviation from its own long-run average. "
                        "Positive = overvalued, negative = undervalued."),

    # ---- Fiscal (FIS) ----------------------------------------------------------------
    RawFieldDef("fiscal_balance_pct_gdp", "Fiscal Balance (% of GDP)", "FIS", "percent", "%",
                frequency="Quarterly", assets=CURRENCIES, has_previous=False),
    RawFieldDef("fiscal_trend", "Fiscal Policy Trend", "FIS", "categorical",
                options=list(FISCAL_TREND_MAPPING.keys()), frequency="Quarterly", assets=CURRENCIES,
                has_previous=False),
    RawFieldDef("debt_to_gdp", "Government Debt / GDP", "FIS", "percent", "%",
                frequency="Quarterly", assets=CURRENCIES, has_previous=False),

    # ---- Central Bank Balance Sheet / Liquidity (CBS) ---------------------------------
    RawFieldDef("balance_sheet_trend", "Central Bank Balance Sheet Trend", "CBS", "categorical",
                options=list(CBS_TREND_MAPPING_FX.keys()), frequency="Monthly", assets=CURRENCIES,
                has_previous=False),
    RawFieldDef("global_liquidity_trend", "Global Liquidity / Major CB Balance Sheets Trend", "CBS", "categorical",
                options=list(GLOBAL_LIQUIDITY_MAPPING_XAU.keys()), frequency="Monthly", assets=["XAU"],
                has_previous=False),

    # ---- Economic Surprises (SURP) ----------------------------------------------------
    RawFieldDef("cpi_surprise", "CPI vs Consensus", "SURP", "categorical",
                options=list(SURPRISE_MAPPING.keys()), frequency="Monthly", assets=CURRENCIES, has_previous=False),
    RawFieldDef("gdp_surprise", "GDP vs Consensus", "SURP", "categorical",
                options=list(SURPRISE_MAPPING.keys()), frequency="Quarterly", assets=CURRENCIES, has_previous=False),
    RawFieldDef("employment_surprise", "Employment Data vs Consensus", "SURP", "categorical",
                options=list(SURPRISE_MAPPING.keys()), frequency="Monthly", assets=CURRENCIES, has_previous=False),
    RawFieldDef("pmi_surprise", "PMI vs Consensus", "SURP", "categorical",
                options=list(SURPRISE_MAPPING.keys()), frequency="Monthly", assets=CURRENCIES, has_previous=False),
    RawFieldDef("surprise_policy_relevance", "Do Recent Surprises Currently Move Policy Expectations?", "SURP",
                "categorical", options=list(SURPRISE_RELEVANCE_MAPPING.keys()), frequency="Irregular",
                assets=CURRENCIES, has_previous=False,
                tooltip="E.g. late-cycle, near a CB decision -> High. Between meetings, priced-in -> Low."),

    # ---- Expectation Changes (EXP) -----------------------------------------------------
    RawFieldDef("priced_rate_change_12m_now", "Priced 12M Rate Change (now, pp)", "EXP", "number", "pp",
                frequency="Daily", assets=CURRENCIES, has_previous=False,
                tooltip="Total hikes(+)/cuts(-) currently priced into the curve over the next 12 months."),
    RawFieldDef("priced_rate_change_12m_1m_ago", "Priced 12M Rate Change (1 month ago, pp)", "EXP", "number", "pp",
                frequency="Daily", assets=CURRENCIES, has_previous=False),

    # ---- Geopolitical / Economic Risk (GEO) --------------------------------------------
    RawFieldDef("geopolitical_impact", "Geopolitical/Policy Impact (economic)", "GEO", "categorical",
                options=list(GEO_IMPACT_MAPPING.keys()), frequency="Irregular", assets=ALL_ASSETS,
                has_previous=False),
    RawFieldDef("geopolitical_confidence", "Confidence in That Assessment", "GEO", "categorical",
                options=list(CONFIDENCE_RELEVANCE_MAPPING.keys()), frequency="Irregular", assets=ALL_ASSETS,
                has_previous=False),
]

FIELD_LABELS = {f.key: f.label for f in RAW_FIELDS}
FIELD_DEFS = {f.key: f for f in RAW_FIELDS}


def fields_for_category(category: str, asset: str = None):
    out = [f for f in RAW_FIELDS if f.category == category]
    if asset:
        out = [f for f in out if f.assets is None or asset in f.assets]
    return out


# ---------------------------------------------------------------------------
# DRIVERS
# ---------------------------------------------------------------------------

DRIVERS = [
    # ================= Monetary Policy & Rate Expectations =================
    DriverDef("rate_trajectory", "Forward Rate Trajectory (12M vs Current)", "MP", "linear_diff_fields",
              {"field_a": "expected_rate_12m", "field_b": "current_policy_rate", "scale": 1.5},
              weight_in_category=1.0, assets=CURRENCIES,
              tooltip="The core FX principle: what markets expect policy to DO, not where it is today."),
    DriverDef("stance_score", "Central Bank Policy Stance", "MP", "categorical",
              {"field": "policy_stance", "mapping": STANCE_MAPPING},
              weight_in_category=0.6, assets=CURRENCIES),
    DriverDef("guidance_score", "Forward Guidance Tone", "MP", "categorical",
              {"field": "forward_guidance_tone", "mapping": GUIDANCE_MAPPING},
              weight_in_category=0.4, assets=CURRENCIES),
    DriverDef("xau_usd_fed_proxy", "USD / Fed Policy Condition (proxy)", "MP", "cross_invert",
              {"source_asset": "USD"}, weight_in_category=1.0, assets=["XAU"],
              tooltip="Gold's monetary-policy driver is the Fed's stance, captured via the computed USD score, "
                      "inverted (a stronger, more hawkish USD is a fundamental headwind for gold)."),

    # ================= Yield Differential =================
    DriverDef("yield_2y_trend", "2Y Yield Trend (1M)", "YD", "linear_trend",
              {"field": "yield_2y", "scale": 0.5}, weight_in_category=0.6, assets=CURRENCIES),
    DriverDef("yield_10y_trend", "10Y Yield Trend (1M)", "YD", "linear_trend",
              {"field": "yield_10y", "scale": 0.5}, weight_in_category=0.4, assets=CURRENCIES),

    # ================= Inflation =================
    DriverDef("inflation_gap_reaction", "Inflation vs Target & Trend", "INF", "inflation_reaction",
              {"field": "cpi_yoy", "target_field": "inflation_target", "scale_gap": 3.0, "scale_trend": 2.0},
              weight_in_category=0.7, assets=CURRENCIES),
    DriverDef("wage_growth_score", "Wage Growth", "INF", "linear_level",
              {"field": "wage_growth", "center": 3.0, "scale": 2.0}, weight_in_category=0.3, assets=CURRENCIES),
    DriverDef("xau_inflation_expectations", "Inflation Expectations Trend", "INF", "linear_trend",
              {"field": "inflation_expectation_10y", "scale": 0.3}, weight_in_category=1.0, assets=["XAU"],
              tooltip="Rising long-run inflation expectations support gold as an inflation hedge."),

    # ================= Labor Market =================
    DriverDef("unemployment_trend", "Unemployment Rate Trend", "LAB", "linear_trend",
              {"field": "unemployment_rate", "scale": 0.3, "invert": True},
              weight_in_category=0.5, assets=CURRENCIES),
    DriverDef("employment_growth_score", "Employment Growth", "LAB", "linear_level",
              {"field": "employment_growth_yoy", "center": 1.0, "scale": 1.5},
              weight_in_category=0.5, assets=CURRENCIES),

    # ================= Growth =================
    DriverDef("gdp_trend", "GDP Growth Trend", "GRW", "linear_trend",
              {"field": "gdp_yoy", "scale": 1.0}, weight_in_category=0.4, assets=CURRENCIES),
    DriverDef("gdp_level", "GDP Growth Level", "GRW", "linear_level",
              {"field": "gdp_yoy", "center": 2.0, "scale": 2.5}, weight_in_category=0.3, assets=CURRENCIES),
    DriverDef("retail_sales_score", "Retail Sales", "GRW", "linear_level",
              {"field": "retail_sales_yoy", "center": 2.0, "scale": 4.0},
              weight_in_category=0.3, assets=CURRENCIES),

    # ================= Economic Momentum =================
    DriverDef("composite_pmi_level", "Composite PMI Level", "MOM", "pmi_level",
              {"fields": ["manuf_pmi", "services_pmi"], "center": 50.0, "scale": 6.0},
              weight_in_category=0.3, assets=CURRENCIES),
    DriverDef("pmi_momentum", "PMI Momentum (Change)", "MOM", "pmi_momentum",
              {"fields": ["manuf_pmi", "services_pmi"], "scale": 3.0},
              weight_in_category=0.45, assets=CURRENCIES,
              tooltip="The brief calls for special weight on the CHANGE in momentum, not just the level."),
    DriverDef("confidence_score", "Consumer Confidence", "MOM", "linear_level",
              {"field": "consumer_confidence", "center": 100.0, "scale": 15.0},
              weight_in_category=0.25, assets=CURRENCIES),

    # ================= Trade / Current Account =================
    DriverDef("current_account_score", "Current Account (% GDP)", "TRD", "linear_level",
              {"field": "current_account_pct_gdp", "center": 0.0, "scale": 4.0},
              weight_in_category=0.6, assets=CURRENCIES),
    DriverDef("trade_trend_score", "Trade Balance Trend", "TRD", "categorical",
              {"field": "trade_balance_trend", "mapping": TREND_MAPPING},
              weight_in_category=0.4, assets=CURRENCIES),

    # ================= Commodities =================
    DriverDef("commodity_momentum_score", "Key Commodity Momentum (3M)", "CMD", "linear_level",
              {"field": "commodity_price_change_3m", "center": 0.0, "scale": 15.0},
              weight_in_category=0.6, assets=["AUD", "CAD", "NZD"]),
    DriverDef("terms_of_trade_score", "Terms of Trade Trend", "CMD", "categorical",
              {"field": "terms_of_trade_trend", "mapping": TREND_MAPPING},
              weight_in_category=0.4, assets=["AUD", "CAD", "NZD"]),

    # ================= China Exposure =================
    DriverDef("china_trajectory_score", "China Macro Trajectory", "CHN", "categorical",
              {"field": "china_trajectory", "mapping": CHINA_TRAJECTORY_MAPPING},
              weight_in_category=0.6, assets=["AUD", "NZD", "CAD"]),
    DriverDef("china_pmi_score", "China Manufacturing PMI", "CHN", "linear_level",
              {"field": "china_pmi", "center": 50.0, "scale": 4.0},
              weight_in_category=0.4, assets=["AUD", "NZD", "CAD"]),

    # ================= Global Risk Sentiment =================
    DriverDef("risk_environment_score", "Global Risk Environment", "RISK", "beta_scaled_categorical",
              {"field": "risk_environment", "mapping": RISK_ENV_MAPPING},
              weight_in_category=0.65, assets=None,
              tooltip="Scaled by this asset's risk-sentiment beta (Model Settings)."),
    DriverDef("vix_trend_score", "Volatility (VIX) Trend", "RISK", "beta_scaled_linear_trend",
              {"field": "vix_level", "scale": 6.0, "invert": True},
              weight_in_category=0.35, assets=None),

    # ================= Safe-Haven Factors =================
    DriverDef("safe_haven_demand_score", "Safe-Haven Demand Signal", "SAFE", "categorical",
              {"field": "safe_haven_demand_signal", "mapping": SAFE_HAVEN_DEMAND_MAPPING},
              weight_in_category=1.0, assets=["USD", "JPY", "CHF", "XAU"]),
    DriverDef("geopolitical_stress_score", "Geopolitical Stress Level", "SAFE", "categorical",
              {"field": "geopolitical_stress_level", "mapping": GEOPOLITICAL_STRESS_MAPPING},
              weight_in_category=1.0, assets=["USD", "JPY", "CHF", "XAU"]),
    DriverDef("etf_flows_score", "Gold ETF Flows", "SAFE", "categorical",
              {"field": "etf_flows_trend", "mapping": ETF_FLOWS_MAPPING},
              weight_in_category=1.0, assets=["XAU"]),
    DriverDef("cb_gold_demand_score", "Central-Bank Gold Demand", "SAFE", "categorical",
              {"field": "cb_gold_demand_trend", "mapping": CB_GOLD_DEMAND_MAPPING},
              weight_in_category=1.0, assets=["XAU"]),

    # ================= CFTC Positioning =================
    DriverDef("positioning_direction", "Net Positioning Direction", "COT", "cot_direction",
              {"field": "net_position_pct_oi", "percentile_field": "position_percentile",
               "sensitivity": 1.5, "crowding_hi": 85, "crowding_lo": 15},
              weight_in_category=0.6, assets=None),
    DriverDef("positioning_momentum", "Positioning Momentum (4W Change)", "COT", "linear_level",
              {"field": "position_change_4w", "center": 0.0, "scale": 15.0},
              weight_in_category=0.4, assets=None),

    # ================= Real Yields =================
    DriverDef("real_yield_fx", "Real Yield Level (10Y - Breakeven)", "RY", "real_yield",
              {"nominal_field": "yield_10y", "infl_exp_field": "inflation_expectation_10y", "scale": 2.0,
               "invert": False}, weight_in_category=1.0, assets=CURRENCIES),
    DriverDef("real_yield_xau", "US Real Yield Level (10Y - Breakeven)", "RY", "real_yield",
              {"nominal_field": "yield_10y", "infl_exp_field": "inflation_expectation_10y", "scale": 2.0,
               "invert": True}, weight_in_category=1.0, assets=["XAU"],
              tooltip="Higher US real yields raise the opportunity cost of holding non-yielding gold "
                      "-- generally bearish; falling real yields are generally supportive, though not an "
                      "absolute rule."),

    # ================= Valuation (REER) =================
    DriverDef("valuation_score", "REER Deviation (mild mean-reversion tilt)", "VAL", "linear_level",
              {"field": "reer_deviation_pct", "center": 0.0, "scale": 20.0, "cap": 40.0, "invert": True},
              weight_in_category=1.0, assets=CURRENCIES,
              tooltip="Capped at +/-40 -- valuation is a secondary factor; an undervalued currency can stay "
                      "undervalued."),

    # ================= Fiscal =================
    DriverDef("fiscal_trend_score", "Fiscal Policy Trend", "FIS", "categorical",
              {"field": "fiscal_trend", "mapping": FISCAL_TREND_MAPPING},
              weight_in_category=0.5, assets=CURRENCIES),
    DriverDef("fiscal_balance_score", "Fiscal Balance (% GDP)", "FIS", "linear_level",
              {"field": "fiscal_balance_pct_gdp", "center": -3.0, "scale": 6.0, "cap": 40.0},
              weight_in_category=0.5, assets=CURRENCIES),

    # ================= Central Bank Balance Sheet =================
    DriverDef("cb_balance_sheet_fx", "Balance Sheet Trend", "CBS", "categorical",
              {"field": "balance_sheet_trend", "mapping": CBS_TREND_MAPPING_FX},
              weight_in_category=1.0, assets=CURRENCIES),
    DriverDef("global_liquidity_xau", "Global Liquidity Trend", "CBS", "categorical",
              {"field": "global_liquidity_trend", "mapping": GLOBAL_LIQUIDITY_MAPPING_XAU},
              weight_in_category=1.0, assets=["XAU"]),

    # ================= Economic Surprises =================
    DriverDef("surprise_composite", "Economic Surprise Composite", "SURP", "surprise_composite",
              {"fields": ["cpi_surprise", "gdp_surprise", "employment_surprise", "pmi_surprise"],
               "mapping": SURPRISE_MAPPING, "relevance_field": "surprise_policy_relevance",
               "relevance_mapping": SURPRISE_RELEVANCE_MAPPING},
              weight_in_category=1.0, assets=CURRENCIES),

    # ================= Expectation Changes =================
    DriverDef("expectation_repricing", "Rate-Path Repricing (1M Change)", "EXP", "expectation_repricing",
              {"field_now": "priced_rate_change_12m_now", "field_prior": "priced_rate_change_12m_1m_ago",
               "scale": 0.5}, weight_in_category=1.0, assets=CURRENCIES,
              tooltip="Captures hawkish/dovish repricing -- one of the strongest fundamental signals per the "
                      "brief -- separately from the MP category's forward-LEVEL driver."),

    # ================= Geopolitical / Economic Risk =================
    DriverDef("geo_score", "Geopolitical/Policy Economic Impact", "GEO", "categorical_scaled",
              {"field": "geopolitical_impact", "mapping": GEO_IMPACT_MAPPING,
               "relevance_field": "geopolitical_confidence", "relevance_mapping": CONFIDENCE_RELEVANCE_MAPPING},
              weight_in_category=1.0, assets=None),
]

DRIVERS_BY_CATEGORY = {}
for _d in DRIVERS:
    DRIVERS_BY_CATEGORY.setdefault(_d.category, []).append(_d)


def drivers_for_asset(asset: str):
    """All drivers applicable to this asset, across all categories."""
    return [d for d in DRIVERS if d.assets is None or asset in d.assets]


def drivers_for_asset_category(asset: str, category: str):
    return [d for d in drivers_for_asset(asset) if d.category == category]
