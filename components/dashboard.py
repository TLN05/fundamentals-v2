"""
components/dashboard.py
========================
The main "Global Fundamental Dashboard" view.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import ASSET_NAMES, ALL_ASSETS


BIAS_COLORS = {
    "Very Bullish": "#0F7B3A", "Bullish": "#3FA34D", "Moderately Bullish": "#8CC63F",
    "Neutral": "#9AA0A6", "Moderately Bearish": "#F4A259", "Bearish": "#E0602B",
    "Very Bearish": "#B02A1E",
}


def render_dashboard(asset_scores: dict, horizon: str):
    st.subheader("Global Fundamental Dashboard")
    st.caption(f"Horizon: {horizon}  --  MODEL RANKING, NOT A PRICE FORECAST.")

    rows = []
    for asset in ALL_ASSETS:
        s = asset_scores.get(asset)
        if not s:
            continue
        rows.append({
            "Asset": asset, "Name": ASSET_NAMES.get(asset, asset),
            "Score": s.final_score, "Bias": s.bias, "Confidence": s.confidence,
            "Alignment": s.alignment, "Data Coverage %": s.data_coverage,
        })
    df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)

    fig = px.bar(
        df, x="Score", y="Asset", orientation="h", color="Bias",
        color_discrete_map=BIAS_COLORS, range_x=[-100, 100],
        hover_data=["Confidence", "Alignment", "Data Coverage %"],
        category_orders={"Asset": list(reversed(df["Asset"]))},
    )
    fig.add_vline(x=0, line_width=1, line_color="gray")
    fig.update_layout(height=430, showlegend=True, legend_title_text="Bias",
                       margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df.style.format({"Score": "{:+.1f}", "Confidence": "{:.0f}%",
                          "Alignment": "{:.0f}%", "Data Coverage %": "{:.0f}%"}),
        use_container_width=True, hide_index=True,
    )

    if not df.empty:
        strongest = df.iloc[0]
        weakest = df.iloc[-1]
        c1, c2 = st.columns(2)
        with c1:
            st.metric(f"Strongest Fundamental: {strongest['Asset']}", f"{strongest['Score']:+.1f}",
                      strongest["Bias"])
        with c2:
            st.metric(f"Weakest Fundamental: {weakest['Asset']}", f"{weakest['Score']:+.1f}",
                      weakest["Bias"])
        st.caption("MODEL RANKING OF CURRENT FUNDAMENTAL SCORES -- NOT A PRICE FORECAST OR TRADE SIGNAL.")
