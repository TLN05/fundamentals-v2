"""
components/matrix.py
=====================
The relative-currency matrix (Section "CURRENCY MATRIX") and the base/quote
pair detail (Section "RELATIVE CURRENCY SCORE"), including a pairwise
Central Bank Divergence readout (Section 21 of the brief -- computed here,
pairwise, rather than as a duplicated standalone per-asset category).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import CURRENCIES, ASSET_NAMES, CENTRAL_BANKS
from scoring_engine import relative_score


def _category_score(asset_score, key):
    for c in asset_score.categories:
        if c.key == key and c.available:
            return c.score
    return None


def render_matrix(asset_scores: dict):
    st.subheader("Currency Matrix -- Relative Fundamental Advantage")
    st.caption("Each cell = Base score minus Quote score, rescaled to -100..+100. "
               "This is a ranking of the MODEL'S CURRENT FUNDAMENTAL SCORES, NOT a prediction of future returns.")

    data = {}
    for base in CURRENCIES:
        row = {}
        for quote in CURRENCIES:
            if base == quote:
                row[quote] = None
            else:
                row[quote] = relative_score(asset_scores[base].final_score, asset_scores[quote].final_score)
        data[base] = row
    df = pd.DataFrame(data).T  # rows = base, cols = quote
    df = df[CURRENCIES].loc[CURRENCIES]

    fig = px.imshow(df, text_auto=".0f", color_continuous_scale="RdYlGn", zmin=-100, zmax=100,
                     labels=dict(x="Quote", y="Base", color="Relative Score"))
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    ranked = sorted(CURRENCIES, key=lambda a: asset_scores[a].final_score, reverse=True)
    st.caption("Ranked strongest to weakest fundamental score: " + " > ".join(ranked))


def render_pair_detail(asset_scores: dict, base: str, quote: str):
    st.subheader(f"{base}/{quote} -- Relative Fundamental Score")
    sa, sb = asset_scores[base], asset_scores[quote]
    rel = relative_score(sa.final_score, sb.final_score)

    c1, c2, c3 = st.columns(3)
    c1.metric(f"{base} Score", f"{sa.final_score:+.1f}", sa.bias)
    c2.metric(f"{quote} Score", f"{sb.final_score:+.1f}", sb.bias)
    c3.metric(f"{base}/{quote} Relative Score", f"{rel:+.1f}",
              f"Advantage: {base}" if rel > 0 else (f"Advantage: {quote}" if rel < 0 else "Balanced"))
    st.caption("Positive = fundamental advantage to the base currency. Negative = advantage to the quote "
               "currency. NOT a guaranteed directional forecast.")

    st.markdown("#### Central Bank Divergence")
    mp_a, mp_b = _category_score(sa, "MP"), _category_score(sb, "MP")
    yd_a, yd_b = _category_score(sa, "YD"), _category_score(sb, "YD")
    if mp_a is not None and mp_b is not None:
        mp_div = round((mp_a - mp_b) / 2.0, 1)
        st.markdown(f"- **Monetary Policy divergence** ({CENTRAL_BANKS.get(base)} vs {CENTRAL_BANKS.get(quote)}): "
                    f"{mp_div:+.1f} -- {'favors ' + base if mp_div > 0 else ('favors ' + quote if mp_div < 0 else 'balanced')}")
    else:
        st.caption("Monetary Policy divergence: insufficient data on one or both sides.")
    if yd_a is not None and yd_b is not None:
        yd_div = round((yd_a - yd_b) / 2.0, 1)
        st.markdown(f"- **Yield Differential divergence**: {yd_div:+.1f} -- "
                    f"{'favors ' + base if yd_div > 0 else ('favors ' + quote if yd_div < 0 else 'balanced')}")
    else:
        st.caption("Yield Differential divergence: insufficient data on one or both sides.")

    st.markdown("#### Category-by-Category Comparison")
    rows = []
    for ca, cb in zip(sa.categories, sb.categories):
        rows.append({
            "Category": ca.label,
            f"{base}": ca.score if ca.available else None,
            f"{quote}": cb.score if cb.available else None,
            "Difference (base - quote)": (ca.score - cb.score) if (ca.available and cb.available) else None,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.style.format({c: "{:+.1f}" for c in df.columns if c != "Category"}, na_rep="N/A"),
                 use_container_width=True, hide_index=True)
