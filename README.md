# FX Fundamental Strength & Macro Bias Engine

A transparent, rules-based (no ML, no black box) macro-fundamental scoring
engine for USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD and Gold (XAU). It answers
**"what is the current fundamental strength/weakness of each asset, why, and
how strong is the evidence?"** -- it deliberately does **not** do technical
analysis, chart patterns, or trade-execution concepts (entries/stops/targets)
and never issues a buy/sell signal.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Click **"Load illustrative sample data"** in the sidebar to explore the app
immediately with clearly-marked placeholder values, or go straight to
**Manual Data Entry** to enter real figures.

## Project layout

```
app.py                     Streamlit entry point / navigation / session state
config.py                  Weights, categories, horizons, bias & alignment thresholds
data_model.py               Standardized schema (RawFieldDef, RawValue, DriverDef, ...)
data_providers/
    base.py                 Abstract DataProvider interface (the API-swap seam)
    manual_provider.py       Version-1 implementation: manual entry, in-memory
metric_catalog.py           Every raw field + every scored driver (data, not logic)
scoring_engine.py           Generic evaluators + hierarchical aggregation + confidence
currency_models.py          Per-asset weight profiles, risk-betas, special-model notes
sample_data.py               Illustrative demo dataset
components/
    dashboard.py             Global ranked dashboard
    currency_detail.py        Per-asset deep dive + full "Score Calculation" table
    matrix.py                 8x8 relative matrix + base/quote pair + CB divergence
    input_forms.py            Manual data-entry UI
    explanations.py           Plain-English narrative generator (grounded in real scores)
utils/
    normalization.py          Generic math helpers (linear scaling, categorical mapping)
    validation.py              Input validation / warnings
```

## The data-provider abstraction (why Version 2 needs zero changes to scoring)

Everything downstream of data entry depends **only** on the abstract
`DataProvider` interface in `data_providers/base.py`:

```python
class DataProvider(ABC):
    def get(self, asset: str, field_key: str) -> Optional[RawValue]: ...
    def set(self, asset: str, field_key: str, raw_value: RawValue) -> None: ...
    def coverage_report(self, asset: str, field_keys) -> float: ...
```

`RawValue` is the one standardized shape every metric takes, regardless of
source: `value, previous_value, forecast, date, source, frequency, notes`.

`scoring_engine.py`, `metric_catalog.py`, `currency_models.py`, and every
component in `components/` call `provider.get(...)` -- never a dict, never
`st.session_state` directly, never a specific provider class. `app.py` is the
**only** place that constructs a concrete provider
(`ManualDataProvider()`).

To plug in a real data vendor later:
1. Create `data_providers/my_api_provider.py` with a class implementing
   `get`, `set` (can raise `NotImplementedError` if read-only), and
   `coverage_report`.
2. In `app.py`, replace `ManualDataProvider()` with `MyApiProvider(...)`
   (or blend both: an API provider for live series, falling back to manual
   overrides -- a "composite" provider is a natural next step and slots into
   the same interface).
3. Nothing in `scoring_engine.py`, `metric_catalog.py`,
   `currency_models.py`, `utils/`, or `components/` needs to change.

This is also why raw fields, drivers, and weights are defined as **data**
(lists of dataclasses in `metric_catalog.py` / dicts in `config.py`) rather
than as inline logic -- a new metric or a reweighted category is a data
change, not a code change.

## Methodology summary

**Architecture.** Strict hierarchy to prevent double-counting:
`raw fields -> driver score (-100..+100) -> category score -> final score`.
A small set of generic, reusable evaluators (`linear_level`, `linear_trend`,
`categorical`, `beta_scaled_categorical`, `real_yield`, `cot_direction`,
`surprise_composite`, `expectation_repricing`, `cross_invert`, etc. -- see
`scoring_engine.EVALUATORS`) interpret the driver definitions in
`metric_catalog.py`; every score is reproducible from the "Score
Calculation" table on the Currency Detail page.

**19 categories**, each independently weighted per asset (see
`config.DEFAULT_BASE_WEIGHTS` / `config.XAU_WEIGHTS`, all editable under
**Model Settings**): Monetary Policy & Rate Expectations, Yield
Differential, Inflation, Labor Market, Growth, Economic Momentum, Trade/
Current Account, Commodities, China Exposure, Global Risk Sentiment,
Safe-Haven Factors, CFTC Positioning, Real Yields, Valuation (REER), Fiscal
Conditions, Central Bank Balance Sheet, Economic Surprises, Expectation
Changes, Geopolitical/Economic Risk.

**Preventing double counting:**
- The absolute policy-rate *level* is never scored on its own -- only the
  *forward trajectory* (expected 12M rate vs current rate) in Monetary
  Policy, which is conceptually distinct from the outright yield level/trend
  scored in Yield Differential (term structure, not central-bank intent).
- Rate-*expectation revisions* (the priced path shifting over the last
  month) live only in **Expectation Changes**, not duplicated inside
  Monetary Policy.
- CPI, its distance from target, and its trend are combined into **one**
  inflation-reaction driver instead of three independent, correlated scores
  that would be summed.
- **Central Bank Divergence** (a pairwise concept) is deliberately *not* a
  20th per-asset category -- it's computed only when comparing two assets
  (`components/matrix.py`, pair view), from each asset's already-computed
  MP and YD category scores, so the same information is never scored twice.
- Commodities / China Exposure / Safe-Haven categories are hard-zeroed for
  assets they don't apply to (via `CATEGORY_ASSET_RESTRICTIONS`) and the
  remaining category weights are renormalized to 100 -- see
  `currency_models._renormalized_profile`.

**Missing data** is never scored as zero. An unavailable driver is dropped
from its category's weighted average with the remaining driver weights
renormalized; a fully-unavailable category is dropped from the final score
the same way. "Data coverage: NN%" reflects this directly (weight-weighted
average of per-category coverage).

**Confidence** (0-100%) is *not* derived from the magnitude of the final
score. It blends: data coverage (30%), the **Fundamental Alignment Score**
(35%) -- the share of "taking a clear stance" category weight that sits on
the majority side, which stays low even when strongly opposing categories
happen to cancel out to a headline-neutral score -- data freshness (20%),
and a positioning-crowding penalty (15%) when CFTC positioning is at a
percentile extreme (crowded, regardless of direction).

**Time horizons.** Short/Medium/Long apply category-weight multipliers
(`config.HORIZON_MULTIPLIERS`) -- e.g. COT and Economic Surprises are
upweighted short-term and downweighted long-term; Valuation and Fiscal are
the reverse; Monetary Policy stays roughly flat across horizons, per the
brief.

**Gold (XAU)** uses an entirely separate weight profile
(`config.XAU_WEIGHTS`), not a currency template: growth/labor/trade/
momentum/fiscal/commodities/China are zeroed, and weight concentrates in
Real Yields, a USD/Fed proxy (computed by inverting the already-computed USD
score -- `cross_invert` evaluator), Global Risk, Safe-Haven/ETF-flows/
CB-demand, Inflation Expectations, Global Liquidity, Positioning, and
Geopolitical Risk.

## Known scope decisions in Version 1

- The metric catalog is comprehensive but representative, not a literal
  1:1 implementation of every single bullet in the original brief (e.g. one
  representative wage-growth field rather than five separate wage series).
  Adding more raw fields/drivers is a data change in `metric_catalog.py`,
  not a redesign.
- "Biggest recent changes" is covered by the Top Positive/Negative Driver
  lists (which are dominated by trend/change-based drivers where data
  supports it) rather than a separate ranked list of deltas.
- Per-driver weights and normalization constants (centers/scales) are
  configured in `metric_catalog.py`; the in-app **Model Settings** page
  exposes category-level weights and risk-betas (the two "knobs" the brief
  calls out most), not every individual driver constant.

## Supabase persistence

See [SUPABASE_SETUP.md](SUPABASE_SETUP.md) for table setup and Streamlit secrets.
