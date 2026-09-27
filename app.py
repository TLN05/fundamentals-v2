"""
app.py
======
FX Fundamental Strength & Macro Bias Engine -- entry point.

This file only wires things together: session state, navigation, and
calling into components/. All calculation lives in scoring_engine.py; all
data storage lives behind data_providers.DataProvider.
"""

from copy import deepcopy

import pandas as pd
import streamlit as st

from config import (
    ALL_ASSETS, CURRENCIES, CATEGORIES, CATEGORY_ORDER, ASSET_NAMES,
    HORIZONS, DEFAULT_HORIZON, HORIZON_MULTIPLIERS,
    DEFAULT_BASE_WEIGHTS, XAU_WEIGHTS, CATEGORY_ASSET_RESTRICTIONS,
)
from currency_models import build_default_weight_profiles, build_default_risk_beta, _renormalized_profile
from data_providers.manual_provider import ManualDataProvider
from scoring_engine import compute_all
from components.dashboard import render_dashboard
from components.currency_detail import render_currency_detail
from components.matrix import render_matrix, render_pair_detail
from components.input_forms import render_asset_input_page
from sample_data import load_sample_data

st.set_page_config(page_title="FX Fundamental Strength & Macro Bias Engine", layout="wide")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state():
    if "provider" not in st.session_state:
        st.session_state.provider = ManualDataProvider()
    if "base_weights" not in st.session_state:
        st.session_state.base_weights = deepcopy(DEFAULT_BASE_WEIGHTS)
    if "xau_weights" not in st.session_state:
        st.session_state.xau_weights = deepcopy(XAU_WEIGHTS)
    if "risk_beta" not in st.session_state:
        st.session_state.risk_beta = build_default_risk_beta()
    if "horizon" not in st.session_state:
        st.session_state.horizon = DEFAULT_HORIZON


def _weight_profiles():
    profiles = {a: _renormalized_profile(a, st.session_state.base_weights) for a in CURRENCIES}
    profiles["XAU"] = _renormalized_profile("XAU", st.session_state.xau_weights)
    return profiles


_init_state()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("FX Fundamental Engine")
st.sidebar.caption("Fundamental strength & macro bias -- not a technical or trade-signal tool.")

page = st.sidebar.radio(
    "Navigate",
    ["Global Dashboard", "Currency Detail", "Currency Matrix", "Manual Data Entry", "Model Settings", "About"],
)

st.session_state.horizon = st.sidebar.selectbox(
    "Time Horizon", HORIZONS, index=HORIZONS.index(st.session_state.horizon)
)

with st.sidebar.expander("Data"):
    if st.button("Load illustrative sample data"):
        load_sample_data(st.session_state.provider)
        st.success("Sample data loaded. This is illustrative, not live data -- replace with real inputs.")
    if st.button("Reset all data"):
        st.session_state.provider = ManualDataProvider()
        st.success("All manual data cleared.")

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

asset_scores = compute_all(
    provider=st.session_state.provider,
    weight_profiles=_weight_profiles(),
    risk_beta=st.session_state.risk_beta,
    horizon=st.session_state.horizon,
    horizon_multipliers=HORIZON_MULTIPLIERS,
)

# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

if page == "Global Dashboard":
    render_dashboard(asset_scores, st.session_state.horizon)

elif page == "Currency Detail":
    asset = st.sidebar.selectbox("Asset", ALL_ASSETS, format_func=lambda a: f"{a} -- {ASSET_NAMES[a]}")
    render_currency_detail(asset_scores[asset], asset)

elif page == "Currency Matrix":
    render_matrix(asset_scores)
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        base = st.selectbox("Base currency", CURRENCIES, index=CURRENCIES.index("AUD"))
    with c2:
        quote = st.selectbox("Quote currency", CURRENCIES, index=CURRENCIES.index("USD"))
    if base != quote:
        render_pair_detail(asset_scores, base, quote)
    else:
        st.info("Choose two different currencies to see a pair comparison.")

elif page == "Manual Data Entry":
    asset = st.sidebar.selectbox("Asset", ALL_ASSETS, format_func=lambda a: f"{a} -- {ASSET_NAMES[a]}")
    render_asset_input_page(asset, st.session_state.provider)

elif page == "Model Settings":
    st.subheader("Model Settings -- Category Weights & Risk Betas")
    st.caption("All weights are transparent and editable here. Category weights are renormalized to 100% "
               "per asset after asset-specific categories (Commodities, China Exposure, Safe-Haven) are "
               "zeroed out for currencies they don't apply to.")

    tab1, tab2, tab3 = st.tabs(["FX Base Weight Profile", "XAU (Gold) Weight Profile", "Risk-Sentiment Betas"])

    with tab1:
        st.markdown("Applies to all 8 currencies, before per-asset renormalization.")
        new_base = {}
        cols = st.columns(2)
        for i, cat in enumerate(CATEGORY_ORDER):
            with cols[i % 2]:
                new_base[cat] = st.number_input(
                    CATEGORIES[cat], min_value=0.0, max_value=100.0,
                    value=float(st.session_state.base_weights[cat]), step=1.0, key=f"base_w_{cat}",
                )
        total = sum(new_base.values())
        st.metric("Sum of weights", f"{total:.1f}%", "will be rescaled to 100% on apply" if total != 100 else "OK")
        if st.button("Apply FX Base Weights"):
            if total > 0:
                st.session_state.base_weights = {k: (v / total) * 100.0 for k, v in new_base.items()}
                st.success("FX base weight profile updated.")

    with tab2:
        st.markdown("Gold uses its own weighting profile (Section 15 of the model brief).")
        new_xau = {}
        cols = st.columns(2)
        for i, cat in enumerate(CATEGORY_ORDER):
            with cols[i % 2]:
                new_xau[cat] = st.number_input(
                    CATEGORIES[cat], min_value=0.0, max_value=100.0,
                    value=float(st.session_state.xau_weights[cat]), step=1.0, key=f"xau_w_{cat}",
                )
        total_x = sum(new_xau.values())
        st.metric("Sum of weights", f"{total_x:.1f}%",
                   "will be rescaled to 100% on apply" if total_x != 100 else "OK")
        if st.button("Apply XAU Weights"):
            if total_x > 0:
                st.session_state.xau_weights = {k: (v / total_x) * 100.0 for k, v in new_xau.items()}
                st.success("XAU weight profile updated.")

    with tab3:
        st.markdown("How strongly each asset responds to Risk-On (+) vs Risk-Off/safe-haven (-) conditions.")
        new_beta = {}
        cols = st.columns(3)
        for i, a in enumerate(ALL_ASSETS):
            with cols[i % 3]:
                new_beta[a] = st.number_input(f"{a} beta", min_value=-1.5, max_value=1.5,
                                               value=float(st.session_state.risk_beta[a]), step=0.1,
                                               key=f"beta_{a}")
        if st.button("Apply Risk Betas"):
            st.session_state.risk_beta = new_beta
            st.success("Risk-sentiment betas updated.")

    st.divider()
    if st.button("Reset everything to model defaults"):
        st.session_state.base_weights = deepcopy(DEFAULT_BASE_WEIGHTS)
        st.session_state.xau_weights = deepcopy(XAU_WEIGHTS)
        st.session_state.risk_beta = build_default_risk_beta()
        st.success("Model settings reset to defaults.")

elif page == "About":
    st.subheader("About This Model")
    st.markdown(
        "This is a **fundamental-only** macro bias engine for USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD and "
        "Gold (XAU). It deliberately excludes technical analysis, chart patterns, and trade-execution "
        "concepts (entries, stops, targets, risk/reward). It answers *what is the current fundamental "
        "strength/weakness of each currency/asset, why, and how strong is the evidence* -- not *should I "
        "buy or sell*.\n\n"
        "Version 1 uses **manual data entry only**. All data flows through a `DataProvider` interface "
        "(see `data_providers/base.py`); a future API-backed provider can replace manual entry without any "
        "change to the scoring engine, normalization, weighting, or UI -- see `README.md`.\n\n"
        "The model is fully **rules-based and deterministic** -- no machine learning, no black box. Every "
        "score is reproducible from the driver table shown on each Currency Detail page."
    )
