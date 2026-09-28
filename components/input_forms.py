"""
components/input_forms.py
==========================
Manual-entry UI. Purely a thin Streamlit layer over ManualDataProvider --
all it does is render widgets, validate what's typed, and write RawValue
objects back into the provider. No scoring logic lives here.
"""

import streamlit as st

from config import CATEGORIES, CATEGORY_ORDER, ASSET_NAMES
from data_model import RawValue
from data_providers.manual_provider import ManualDataProvider
from metric_catalog import fields_for_category
from utils.validation import validate_percent, validate_date_str, validate_categorical

FREQ_OPTIONS = ["Daily", "Weekly", "Monthly", "Quarterly", "Irregular"]


def _render_field(asset: str, field, provider: ManualDataProvider):
    current = provider.get_or_empty(asset, field.key)
    prefix = f"{asset}_{field.key}"
    warnings = []

    cols = st.columns([2, 1, 1] if field.field_type != "categorical" else [2, 1])

    with cols[0]:
        if field.field_type == "categorical":
            options = ["(not entered)"] + list(field.options or [])
            idx = options.index(current.value) if current.value in options else 0
            value = st.selectbox(field.label, options, index=idx, key=f"{prefix}_value", help=field.tooltip)
            value = None if value == "(not entered)" else value
            warnings += validate_categorical(value, field.options or [], field.label)
        else:
            raw_default = current.value if current.value is not None else None
            value = st.number_input(
                f"{field.label} ({field.unit})" if field.unit else field.label,
                value=float(raw_default) if raw_default is not None else 0.0,
                step=0.01 if field.field_type == "percent" else 1.0,
                format="%.3f" if field.field_type == "percent" else "%.2f",
                key=f"{prefix}_value", help=field.tooltip,
            )
            if raw_default is None and value == 0.0:
                # Ambiguous: user may genuinely mean 0.0, or may not have touched the field.
                # We keep 0.0 as a valid entry once the widget has been rendered; a small
                # checkbox lets the user explicitly mark it unavailable instead.
                pass
            if field.field_type == "percent":
                warnings += validate_percent(value, field.label)

    prev_val = current.previous_value
    forecast_val = current.forecast
    if field.field_type != "categorical":
        if field.has_previous:
            with cols[1]:
                prev_val = st.number_input(
                    "Previous", value=float(prev_val) if prev_val is not None else 0.0,
                    step=0.01 if field.field_type == "percent" else 1.0,
                    format="%.3f" if field.field_type == "percent" else "%.2f",
                    key=f"{prefix}_prev",
                )
        if field.has_forecast:
            with cols[2 if field.has_previous else 1]:
                forecast_val = st.number_input(
                    "Forecast/Consensus", value=float(forecast_val) if forecast_val is not None else 0.0,
                    step=0.01, format="%.3f", key=f"{prefix}_fcst",
                )

    mark_unavailable = st.checkbox("Mark unavailable / not entered", key=f"{prefix}_na",
                                    value=current.value is None)

    with st.expander(f"Source & date -- {field.label}", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            date_val = st.text_input("Date (YYYY-MM-DD)", value=current.date or "", key=f"{prefix}_date")
            warnings += validate_date_str(date_val, field.label)
        with c2:
            source_val = st.text_input("Source", value=current.source or "", key=f"{prefix}_source")
        with c3:
            freq_default = current.frequency or field.frequency
            freq_val = st.selectbox("Frequency", FREQ_OPTIONS,
                                     index=FREQ_OPTIONS.index(freq_default) if freq_default in FREQ_OPTIONS else 2,
                                     key=f"{prefix}_freq")
        notes_val = st.text_input("Notes", value=current.notes or "", key=f"{prefix}_notes")

    for w in warnings:
        st.warning(w)

    new_rv = RawValue(
        value=None if mark_unavailable else value,
        previous_value=prev_val if field.has_previous and not mark_unavailable else None,
        forecast=forecast_val if field.has_forecast and not mark_unavailable else None,
        date=date_val or None,
        source=source_val or None,
        frequency=freq_val,
        notes=notes_val or None,
    )
    provider.set(asset, field.key, new_rv)


def render_asset_input_page(asset: str, provider: ManualDataProvider):
    st.subheader(f"Manual Fundamental Inputs -- {ASSET_NAMES.get(asset, asset)} ({asset})")
    st.caption("Every field can be left as 'not entered' -- the model will mark it Unavailable and "
               "renormalize the remaining weights rather than assuming a value.")

    tabs_categories = [c for c in CATEGORY_ORDER if fields_for_category(c, asset)]
    tabs = st.tabs([CATEGORIES[c] for c in tabs_categories])
    for tab, cat_key in zip(tabs, tabs_categories):
        with tab:
            fields = fields_for_category(cat_key, asset)
            for field in fields:
                _render_field(asset, field, provider)
                st.divider()
