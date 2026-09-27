"""
components/currency_detail.py
==============================
Deep-dive page for a single asset: final score, category breakdown, full
driver-level "Score Calculation" transparency table, top drivers, data
quality, and the generated explanation narrative.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import ASSET_NAMES, CENTRAL_BANKS
from currency_models import SPECIAL_MODEL_NOTES
from components.explanations import build_summary, biggest_risks
from config import FRESHNESS_MISSING


def render_currency_detail(asset_score, asset: str):
    st.subheader(f"{ASSET_NAMES.get(asset, asset)} ({asset}) -- Fundamental Detail")
    st.caption(f"Central bank: {CENTRAL_BANKS.get(asset, 'N/A')}  |  Horizon: {asset_score.horizon}  |  "
               f"As of {asset_score.as_of}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Fundamental Score", f"{asset_score.final_score:+.1f}", asset_score.bias)
    c2.metric("Confidence", f"{asset_score.confidence:.0f}%")
    c3.metric("Fundamental Alignment", f"{asset_score.alignment:.0f}%")
    c4.metric("Data Coverage", f"{asset_score.data_coverage:.0f}%")

    if asset_score.conflict_note:
        st.warning(asset_score.conflict_note)

    st.info(SPECIAL_MODEL_NOTES.get(asset, ""), icon="ℹ️")

    st.markdown("#### Category Breakdown")
    cat_rows = [{
        "Category": c.label, "Score": c.score if c.available else None,
        "Weight %": round(c.weight, 1), "Contribution": c.contribution,
        "Coverage %": round(c.coverage * 100, 0), "Status": "Available" if c.available else "Unavailable",
    } for c in asset_score.categories]
    cat_df = pd.DataFrame(cat_rows)
    plot_df = cat_df.dropna(subset=["Score"])
    if not plot_df.empty:
        fig = px.bar(plot_df.sort_values("Score"), x="Score", y="Category", orientation="h",
                     range_x=[-100, 100], color="Score", color_continuous_scale="RdYlGn",
                     range_color=[-100, 100])
        fig.add_vline(x=0, line_width=1, line_color="gray")
        fig.update_layout(height=520, coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cat_df.style.format({"Score": "{:+.1f}", "Contribution": "{:+.2f}"}, na_rep="N/A"),
                 use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Top Positive Drivers")
        if asset_score.top_bullish:
            for d in asset_score.top_bullish:
                st.markdown(f"- **{d.label}** ({d.score:+.1f}): {d.explanation}")
        else:
            st.caption("No positive drivers with available data.")
    with col_b:
        st.markdown("#### Top Negative Drivers")
        if asset_score.top_bearish:
            for d in asset_score.top_bearish:
                st.markdown(f"- **{d.label}** ({d.score:+.1f}): {d.explanation}")
        else:
            st.caption("No negative drivers with available data.")

    st.markdown("#### Biggest Risks to the Current Fundamental Thesis")
    risks = biggest_risks(asset_score)
    if risks:
        for r in risks:
            st.markdown(f"- {r}")
    else:
        st.caption("No material offsetting risks identified from current data.")

    st.markdown("#### Explanation")
    st.markdown(build_summary(asset_score))

    with st.expander("Score Calculation -- full transparency (every driver, reproducible)", expanded=False):
        driver_rows = []
        for c in asset_score.categories:
            for d in c.drivers:
                # Renormalize this driver's weight among only the AVAILABLE drivers in its
                # category (c.coverage = sum of weight_in_category over available drivers) so
                # the displayed contribution always reproduces the category score exactly,
                # matching how missing data is excluded-and-renormalized rather than zeroed.
                renorm_weight = (d.weight_in_category / c.coverage) if (d.available and c.coverage > 0) else None
                driver_rows.append({
                    "Category": c.label, "Driver": d.label,
                    "Score": d.score if d.available else None,
                    "Weight in Category (renormalized)": round(renorm_weight, 3) if renorm_weight is not None else None,
                    "Category Weight %": round(c.weight, 1),
                    "Contribution": round((c.weight / 100.0) * renorm_weight * d.score, 2) if renorm_weight is not None else None,
                    "Freshness": d.freshness, "Data Date": d.data_date or "--",
                    "Status": "Available" if d.available else "Unavailable",
                    "Explanation": d.explanation,
                })
        ddf = pd.DataFrame(driver_rows)
        st.dataframe(ddf.style.format({"Score": "{:+.1f}", "Contribution": "{:+.3f}"}, na_rep="N/A"),
                     use_container_width=True, hide_index=True)
        st.caption("Final Score = sum over available categories of (renormalized Category Weight% / 100) x "
                   "Category Score. Category Score = sum over available drivers of (renormalized Driver "
                   "Weight-in-Category) x Driver Score. Unavailable metrics are excluded, never zeroed, and "
                   "the remaining weights are renormalized -- this is why weights shown here can differ from "
                   "the configured defaults in Model Settings when data is incomplete.")
