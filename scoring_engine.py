"""
scoring_engine.py
==================
Pure calculation layer. Knows nothing about Streamlit. Depends only on:
  - data_model            (schema)
  - data_providers.base   (DataProvider interface)
  - metric_catalog        (raw fields + driver definitions)
  - currency_models       (per-asset weight profiles, risk betas)
  - config                (bias thresholds, alignment thresholds, horizons)

Aggregation is strictly hierarchical, by design, to prevent double-counting:

    raw fields  -->  driver score (-100..100)
    driver scores, weighted within their category  -->  category score
    category scores, weighted per the asset's profile  -->  final score

Missing data is never scored as zero. A driver with insufficient data is
`available=False` / `score=None` and is dropped from its category's
weighted average, with the remaining driver weights renormalized. The same
happens one level up: a category with zero available drivers is dropped
from the final weighted average, with remaining category weights
renormalized. This is what makes "Data coverage: NN%" meaningful.
"""

from typing import Dict, List, Optional

from config import (
    CATEGORIES, ALIGNMENT_NEUTRAL_BAND, ALIGNMENT_MIXED_THRESHOLD,
    score_to_bias, FRESHNESS_FRESH, FRESHNESS_AGING, FRESHNESS_STALE, FRESHNESS_MISSING,
)
from data_model import DriverScore, CategoryScore, AssetScore, RawValue
from data_providers.base import DataProvider
from metric_catalog import FIELD_LABELS, drivers_for_asset_category
from utils.normalization import clip, linear_score, weighted_average

FRESHNESS_RANK = {FRESHNESS_STALE: 0, FRESHNESS_AGING: 1, FRESHNESS_FRESH: 2, FRESHNESS_MISSING: -1}
FRESHNESS_CONF = {FRESHNESS_FRESH: 100.0, FRESHNESS_AGING: 55.0, FRESHNESS_STALE: 15.0}


def _get(provider: DataProvider, asset: str, field: str) -> RawValue:
    return provider.get_or_empty(asset, field)


def _label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


# ---------------------------------------------------------------------------
# Evaluators -- one function per eval_type used in metric_catalog.DRIVERS.
# Each returns a dict: {"score": float|None, "explanation": str, "raw": {field: RawValue},
#                        "crowding_flag": bool (optional)}
# ---------------------------------------------------------------------------

def ev_categorical(asset, provider, params, context):
    field, mapping = params["field"], params["mapping"]
    rv = _get(provider, asset, field)
    raw = {field: rv}
    if not rv.is_populated():
        return {"score": None, "explanation": f"{_label(field)} not entered.", "raw": raw}
    score = mapping.get(rv.value)
    if score is None:
        return {"score": None, "explanation": f"{_label(field)} value '{rv.value}' not recognized.", "raw": raw}
    return {"score": score, "explanation": f"{_label(field)} = '{rv.value}' -> {score:+.0f}", "raw": raw}


def ev_categorical_scaled(asset, provider, params, context):
    field, mapping = params["field"], params["mapping"]
    rf, rmap = params["relevance_field"], params["relevance_mapping"]
    rv, rvrel = _get(provider, asset, field), _get(provider, asset, rf)
    raw = {field: rv, rf: rvrel}
    if not rv.is_populated():
        return {"score": None, "explanation": f"{_label(field)} not entered.", "raw": raw}
    base = mapping.get(rv.value)
    if base is None:
        return {"score": None, "explanation": f"Unrecognized value '{rv.value}'.", "raw": raw}
    relevance = rmap.get(rvrel.value, 0.7) if rvrel.is_populated() else 0.7
    score = clip(base * relevance)
    return {"score": score,
            "explanation": f"{rv.value} ({_label(field)}) x confidence "
                            f"{rvrel.value if rvrel.is_populated() else 'Medium (assumed)'} -> {score:+.1f}",
            "raw": raw}


def ev_linear_level(asset, provider, params, context):
    field = params["field"]
    center, scale, cap = params.get("center", 0.0), params["scale"], params.get("cap", 100.0)
    invert = params.get("invert", False)
    rv = _get(provider, asset, field)
    raw = {field: rv}
    if not rv.is_populated():
        return {"score": None, "explanation": f"{_label(field)} not entered.", "raw": raw}
    try:
        val = float(rv.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": f"{_label(field)} value is not numeric.", "raw": raw}
    score = linear_score(val, center, scale, cap)
    if invert:
        score = -score
    return {"score": score, "explanation": f"{_label(field)} = {val:g} (baseline {center:g}) -> {score:+.1f}",
            "raw": raw}


def ev_linear_trend(asset, provider, params, context):
    field, scale, cap = params["field"], params["scale"], params.get("cap", 100.0)
    invert = params.get("invert", False)
    rv = _get(provider, asset, field)
    raw = {field: rv}
    if not rv.is_populated() or rv.previous_value is None:
        return {"score": None, "explanation": f"{_label(field)} current/previous value incomplete.", "raw": raw}
    try:
        diff = float(rv.value) - float(rv.previous_value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": f"{_label(field)} values are not numeric.", "raw": raw}
    score = linear_score(diff, 0.0, scale, cap)
    if invert:
        score = -score
    return {"score": score,
            "explanation": f"{_label(field)} changed {diff:+.2f} vs previous reading -> {score:+.1f}", "raw": raw}


def ev_linear_diff_fields(asset, provider, params, context):
    fa, fb, scale, cap = params["field_a"], params["field_b"], params["scale"], params.get("cap", 100.0)
    rva, rvb = _get(provider, asset, fa), _get(provider, asset, fb)
    raw = {fa: rva, fb: rvb}
    if not rva.is_populated() or not rvb.is_populated():
        return {"score": None, "explanation": "Required fields not fully entered.", "raw": raw}
    try:
        diff = float(rva.value) - float(rvb.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": "Values are not numeric.", "raw": raw}
    score = linear_score(diff, 0.0, scale, cap)
    return {"score": score,
            "explanation": f"{_label(fa)} ({rva.value:g}) vs {_label(fb)} ({rvb.value:g}): "
                            f"{diff:+.2f} -> {score:+.1f}", "raw": raw}


def ev_beta_scaled_categorical(asset, provider, params, context):
    field, mapping = params["field"], params["mapping"]
    rv = _get(provider, asset, field)
    raw = {field: rv}
    beta = context.get("risk_beta", {}).get(asset, 0.5)
    if not rv.is_populated():
        return {"score": None, "explanation": f"{_label(field)} not entered.", "raw": raw}
    base = mapping.get(rv.value)
    if base is None:
        return {"score": None, "explanation": f"Unrecognized value '{rv.value}'.", "raw": raw}
    score = clip(base * beta)
    return {"score": score,
            "explanation": f"'{rv.value}' backdrop x {asset} risk-beta ({beta:+.2f}) -> {score:+.1f}", "raw": raw}


def ev_beta_scaled_linear_trend(asset, provider, params, context):
    field, scale, invert = params["field"], params["scale"], params.get("invert", False)
    rv = _get(provider, asset, field)
    raw = {field: rv}
    beta = context.get("risk_beta", {}).get(asset, 0.5)
    if not rv.is_populated() or rv.previous_value is None:
        return {"score": None, "explanation": f"{_label(field)} current/previous value incomplete.", "raw": raw}
    try:
        diff = float(rv.value) - float(rv.previous_value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": f"{_label(field)} values are not numeric.", "raw": raw}
    base = linear_score(diff, 0.0, scale)
    if invert:
        base = -base
    score = clip(base * beta)
    return {"score": score,
            "explanation": f"{_label(field)} changed {diff:+.2f}; x {asset} risk-beta ({beta:+.2f}) -> {score:+.1f}",
            "raw": raw}


def ev_inflation_reaction(asset, provider, params, context):
    field, target_field = params["field"], params["target_field"]
    scale_gap, scale_trend = params["scale_gap"], params["scale_trend"]
    rv, tv = _get(provider, asset, field), _get(provider, asset, target_field)
    raw = {field: rv, target_field: tv}
    if not rv.is_populated() or not tv.is_populated():
        return {"score": None, "explanation": "CPI or inflation target not entered.", "raw": raw}
    try:
        gap = float(rv.value) - float(tv.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": "CPI/target values are not numeric.", "raw": raw}
    gap_score = linear_score(gap, 0.0, scale_gap)
    trend_score = None
    trend = None
    if rv.previous_value is not None:
        try:
            trend = float(rv.value) - float(rv.previous_value)
            trend_score = linear_score(trend, 0.0, scale_trend)
        except (TypeError, ValueError):
            trend_score = None
    score = weighted_average([(gap_score, 0.5), (trend_score, 0.5)]) if trend_score is not None else gap_score
    expl = f"CPI {rv.value:g}% vs target {tv.value:g}% (gap {gap:+.2f}pp)"
    if trend_score is not None:
        expl += f", trend {trend:+.2f}pp"
    expl += f" -> {score:+.1f} (not automatically bullish/bearish -- reaction-conditioned)"
    return {"score": score, "explanation": expl, "raw": raw}


def ev_pmi_level(asset, provider, params, context):
    fields, center, scale = params["fields"], params.get("center", 50.0), params["scale"]
    raws, vals = {}, []
    for f in fields:
        rv = _get(provider, asset, f)
        raws[f] = rv
        if rv.is_populated():
            try:
                vals.append(float(rv.value))
            except (TypeError, ValueError):
                pass
    if not vals:
        return {"score": None, "explanation": "No PMI level data entered.", "raw": raws}
    avg = sum(vals) / len(vals)
    score = linear_score(avg, center, scale)
    return {"score": score, "explanation": f"Composite PMI avg {avg:.1f} (baseline {center:g}) -> {score:+.1f}",
            "raw": raws}


def ev_pmi_momentum(asset, provider, params, context):
    fields, scale = params["fields"], params["scale"]
    raws, diffs = {}, []
    for f in fields:
        rv = _get(provider, asset, f)
        raws[f] = rv
        if rv.is_populated() and rv.previous_value is not None:
            try:
                diffs.append(float(rv.value) - float(rv.previous_value))
            except (TypeError, ValueError):
                pass
    if not diffs:
        return {"score": None, "explanation": "No PMI trend data entered.", "raw": raws}
    avg = sum(diffs) / len(diffs)
    score = linear_score(avg, 0.0, scale)
    return {"score": score, "explanation": f"PMI momentum avg change {avg:+.2f}pt -> {score:+.1f}", "raw": raws}


def ev_real_yield(asset, provider, params, context):
    nf, iff = params["nominal_field"], params["infl_exp_field"]
    scale, invert = params["scale"], params.get("invert", False)
    rvn, rvi = _get(provider, asset, nf), _get(provider, asset, iff)
    raw = {nf: rvn, iff: rvi}
    if not rvn.is_populated() or not rvi.is_populated():
        return {"score": None, "explanation": "Nominal yield or inflation expectations not entered.", "raw": raw}
    try:
        real = float(rvn.value) - float(rvi.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": "Yield/expectation values are not numeric.", "raw": raw}
    score = linear_score(real, 0.0, scale)
    if invert:
        score = -score
    return {"score": score,
            "explanation": f"Approx. real yield {real:+.2f}% ({rvn.value:g}% nominal - "
                            f"{rvi.value:g}% breakeven) -> {score:+.1f}", "raw": raw}


def ev_cot_direction(asset, provider, params, context):
    field, pf = params["field"], params["percentile_field"]
    sens, hi, lo = params.get("sensitivity", 1.5), params.get("crowding_hi", 85), params.get("crowding_lo", 15)
    rv, pv = _get(provider, asset, field), _get(provider, asset, pf)
    raw = {field: rv, pf: pv}
    if not rv.is_populated():
        return {"score": None, "explanation": "Net positioning not entered.", "raw": raw}
    try:
        net = float(rv.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": "Net positioning value is not numeric.", "raw": raw}
    score = clip(net * sens)
    crowding = False
    if pv.is_populated():
        try:
            pct = float(pv.value)
            crowding = pct >= hi or pct <= lo
        except (TypeError, ValueError):
            pass
    expl = f"Net positioning {net:+.1f}% of OI -> {score:+.1f}"
    if crowding:
        expl += " (positioning percentile flags crowding -- reversal risk, shown separately from direction)"
    return {"score": score, "explanation": expl, "raw": raw, "crowding_flag": crowding}


def ev_surprise_composite(asset, provider, params, context):
    fields, mapping = params["fields"], params["mapping"]
    rf, rmap = params["relevance_field"], params["relevance_mapping"]
    raws, vals = {}, []
    for f in fields:
        rv = _get(provider, asset, f)
        raws[f] = rv
        if rv.is_populated() and rv.value in mapping:
            vals.append(mapping[rv.value])
    rvrel = _get(provider, asset, rf)
    raws[rf] = rvrel
    if not vals:
        return {"score": None, "explanation": "No data-surprise readings entered.", "raw": raws}
    avg = sum(vals) / len(vals)
    relevance = rmap.get(rvrel.value, 0.6) if rvrel.is_populated() else 0.6
    score = clip(avg * relevance)
    return {"score": score,
            "explanation": f"Avg surprise reading {avg:+.1f} x policy-relevance "
                            f"{relevance:.1f} -> {score:+.1f}", "raw": raws}


def ev_expectation_repricing(asset, provider, params, context):
    fn, fp, scale = params["field_now"], params["field_prior"], params["scale"]
    rvn, rvp = _get(provider, asset, fn), _get(provider, asset, fp)
    raw = {fn: rvn, fp: rvp}
    if not rvn.is_populated() or not rvp.is_populated():
        return {"score": None, "explanation": "Current/prior priced rate path not entered.", "raw": raw}
    try:
        diff = float(rvn.value) - float(rvp.value)
    except (TypeError, ValueError):
        return {"score": None, "explanation": "Priced rate path values are not numeric.", "raw": raw}
    score = linear_score(diff, 0.0, scale)
    direction = "hawkish repricing" if diff > 0 else ("dovish repricing" if diff < 0 else "no change")
    return {"score": score,
            "explanation": f"Priced 12M rate path moved {diff:+.2f}pp vs 1 month ago "
                            f"({direction}) -> {score:+.1f}", "raw": raw}


def ev_cross_invert(asset, provider, params, context):
    source_asset = params["source_asset"]
    other_scores = context.get("other_scores", {})
    src = other_scores.get(source_asset)
    if src is None:
        return {"score": None, "explanation": f"{source_asset} score not yet available.", "raw": {}}
    score = clip(-1 * src.final_score)
    return {"score": score,
            "explanation": f"{source_asset} fundamental score is {src.final_score:+.1f} ({src.bias}); "
                            f"gold is modeled as reacting inversely -> {score:+.1f}", "raw": {}}


EVALUATORS = {
    "categorical": ev_categorical,
    "categorical_scaled": ev_categorical_scaled,
    "linear_level": ev_linear_level,
    "linear_trend": ev_linear_trend,
    "linear_diff_fields": ev_linear_diff_fields,
    "beta_scaled_categorical": ev_beta_scaled_categorical,
    "beta_scaled_linear_trend": ev_beta_scaled_linear_trend,
    "inflation_reaction": ev_inflation_reaction,
    "pmi_level": ev_pmi_level,
    "pmi_momentum": ev_pmi_momentum,
    "real_yield": ev_real_yield,
    "cot_direction": ev_cot_direction,
    "surprise_composite": ev_surprise_composite,
    "expectation_repricing": ev_expectation_repricing,
    "cross_invert": ev_cross_invert,
}


def _worst_freshness(raw_values: Dict[str, RawValue]) -> str:
    if not raw_values:
        return FRESHNESS_FRESH  # computed/cross-asset drivers have no raw fields of their own
    worst = FRESHNESS_FRESH
    for rv in raw_values.values():
        f = rv.freshness()
        if FRESHNESS_RANK[f] < FRESHNESS_RANK[worst]:
            worst = f
    return worst


def _primary_date(raw_values: Dict[str, RawValue]) -> Optional[str]:
    for rv in raw_values.values():
        if rv.date:
            return rv.date
    return None


def compute_driver_score(driver_def, asset: str, provider: DataProvider, context: dict) -> DriverScore:
    fn = EVALUATORS[driver_def.eval_type]
    result = fn(asset, provider, driver_def.params, context)
    raw = result.get("raw", {})
    freshness = _worst_freshness(raw)
    return DriverScore(
        key=driver_def.key,
        label=driver_def.label,
        category=driver_def.category,
        score=result.get("score"),
        weight_in_category=driver_def.weight_in_category,  # raw weight; renormalized in compute_category_score
        explanation=result.get("explanation", ""),
        raw=raw,
        available=result.get("score") is not None,
        freshness=freshness if result.get("score") is not None else FRESHNESS_MISSING,
        data_date=_primary_date(raw),
        crowding_flag=result.get("crowding_flag", False),
    )


def compute_category_score(category_key: str, asset: str, provider: DataProvider,
                            base_weight: float, context: dict) -> CategoryScore:
    driver_defs = drivers_for_asset_category(asset, category_key)
    driver_scores = [compute_driver_score(d, asset, provider, context) for d in driver_defs]

    total_cfg_weight = sum(d.weight_in_category for d in driver_scores) or 1.0
    for d in driver_scores:
        d.weight_in_category = d.weight_in_category / total_cfg_weight  # now sums to 1 among applicable drivers

    available = [d for d in driver_scores if d.available]
    coverage = sum(d.weight_in_category for d in available)
    if available:
        score = weighted_average([(d.score, d.weight_in_category) for d in available])
    else:
        score = None

    return CategoryScore(
        key=category_key,
        label=CATEGORIES[category_key],
        score=score,
        weight=base_weight,       # filled in / renormalized by caller (compute_asset_score)
        base_weight=base_weight,
        contribution=0.0,          # filled in by caller once final weight is known
        drivers=driver_scores,
        coverage=coverage,
        available=score is not None,
    )


def compute_confidence(categories: List[CategoryScore]) -> float:
    all_drivers = [d for c in categories for d in c.drivers]
    available = [d for d in all_drivers if d.available]

    total_w = sum(c.weight for c in categories) or 1.0
    coverage_pct = 100.0 * sum(c.weight * c.coverage for c in categories) / total_w

    weighted_fresh = []
    for c in categories:
        if not c.available or c.coverage <= 0:
            continue
        for d in c.drivers:
            if d.available:
                renorm = d.weight_in_category / c.coverage
                w = (c.weight / total_w) * renorm
                weighted_fresh.append((FRESHNESS_CONF.get(d.freshness, 55.0), w))
    freshness_pct = weighted_average(weighted_fresh)
    if freshness_pct is None:
        freshness_pct = 0.0

    crowded = any(d.crowding_flag for d in available)
    crowding_component = 70.0 if crowded else 100.0

    final_score = weighted_average([(c.score, c.weight) for c in categories if c.available])
    alignment = compute_alignment(categories, final_score if final_score is not None else 0.0)

    confidence = (0.30 * coverage_pct) + (0.35 * alignment) + (0.20 * freshness_pct) + (0.15 * crowding_component)
    return round(clip(confidence, 0, 100), 1)


def compute_alignment(categories: List[CategoryScore], final_score: float = 0.0) -> float:
    """Fundamental Alignment Score: what share of the weight that IS taking a
    clear directional stance (|score| > neutral band) sits on the majority
    side. This is independent of whether the final score itself nets out to
    Neutral -- strong bullish and bearish categories that cancel each other
    out are exactly the "mixed fundamental environment" case the brief asks
    to surface, even though the headline score looks calm."""
    bullish_w = sum(c.weight for c in categories if c.available and c.score > ALIGNMENT_NEUTRAL_BAND)
    bearish_w = sum(c.weight for c in categories if c.available and c.score < -ALIGNMENT_NEUTRAL_BAND)
    directional = bullish_w + bearish_w
    if directional == 0:
        return 100.0  # nothing is taking a strong stance either way -- no disagreement to speak of
    majority = max(bullish_w, bearish_w)
    return round(100.0 * majority / directional, 1)


def compute_asset_score(asset: str, provider: DataProvider, weight_profile: Dict[str, float],
                         risk_beta: Dict[str, float], horizon: str, horizon_multipliers: Dict[str, dict],
                         other_scores: Optional[Dict[str, AssetScore]] = None) -> AssetScore:
    context = {"risk_beta": risk_beta, "other_scores": other_scores or {}}

    # Apply horizon multipliers to the asset's category weight profile, then renormalize to 100.
    mult = horizon_multipliers.get(horizon, {})
    adjusted = {k: w * mult.get(k, 1.0) for k, w in weight_profile.items()}
    total = sum(adjusted.values()) or 1.0
    normalized_weights = {k: (w / total) * 100.0 for k, w in adjusted.items()}

    categories = []
    for cat_key, base_weight in normalized_weights.items():
        cat_score = compute_category_score(cat_key, asset, provider, base_weight, context)
        categories.append(cat_score)

    # Renormalize weight across categories with available data, then compute contributions.
    avail_categories = [c for c in categories if c.available]
    avail_total_weight = sum(c.weight for c in avail_categories) or 1.0
    for c in categories:
        if c.available:
            c.weight = (c.weight / avail_total_weight) * 100.0
            c.contribution = round((c.weight / 100.0) * c.score, 2)
        else:
            c.weight = 0.0
            c.contribution = 0.0

    final_score = weighted_average([(c.score, c.weight) for c in avail_categories])
    final_score = round(final_score, 1) if final_score is not None else 0.0
    bias = score_to_bias(final_score)

    confidence = compute_confidence(categories)
    alignment = compute_alignment(categories, final_score)
    conflict_note = ("Mixed fundamental environment -- major categories disagree materially with the "
                      "model's overall direction." if alignment < ALIGNMENT_MIXED_THRESHOLD else None)

    total_cat_weight = sum(c.base_weight for c in categories) or 1.0
    data_coverage = round(100.0 * sum(c.base_weight * c.coverage for c in categories) / total_cat_weight, 1)

    all_drivers = [d for c in categories for d in c.drivers if d.available]
    all_drivers_sorted = sorted(all_drivers, key=lambda d: d.score, reverse=True)
    top_bullish = [d for d in all_drivers_sorted if d.score > 0][:5]
    top_bearish = [d for d in reversed(all_drivers_sorted) if d.score < 0][:5]

    from datetime import date
    return AssetScore(
        asset=asset, horizon=horizon, final_score=final_score, bias=bias, confidence=confidence,
        alignment=alignment, data_coverage=data_coverage, categories=categories,
        top_bullish=top_bullish, top_bearish=top_bearish, conflict_note=conflict_note,
        as_of=date.today().isoformat(),
    )


def compute_all(provider: DataProvider, weight_profiles: Dict[str, Dict[str, float]],
                 risk_beta: Dict[str, float], horizon: str,
                 horizon_multipliers: Dict[str, dict]) -> Dict[str, AssetScore]:
    """Compute every FX currency first, then XAU (which cross-references USD's
    computed score for its Fed/USD-condition driver)."""
    from config import CURRENCIES
    results: Dict[str, AssetScore] = {}
    for asset in CURRENCIES:
        results[asset] = compute_asset_score(asset, provider, weight_profiles[asset], risk_beta, horizon,
                                              horizon_multipliers, other_scores=results)
    if "XAU" in weight_profiles:
        results["XAU"] = compute_asset_score("XAU", provider, weight_profiles["XAU"], risk_beta, horizon,
                                              horizon_multipliers, other_scores=results)
    return results


def relative_score(score_a: float, score_b: float) -> float:
    """AssetA - AssetB, normalized back into -100..100 (raw diff can be -200..200)."""
    return round(clip((score_a - score_b) / 2.0), 1)
