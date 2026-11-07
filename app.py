import os
import pandas as pd
import streamlit as st

# Automatically bridge Streamlit Secrets to environment variables if present
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

if "META_ACCESS_TOKEN" in st.secrets:
    os.environ["META_ACCESS_TOKEN"] = st.secrets["META_ACCESS_TOKEN"]

from pipeline import run_end_to_end_competitor_pipeline

st.set_page_config(page_title="Competitor Ad Intelligence", page_icon="⚡", layout="wide")
st.title("⚡ AI Competitor Ad Intelligence & Brief Generator")

with st.sidebar:
    st.header("🔑 API Configurations")
    openai_input = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    meta_input = st.text_input("Meta Graph Access Token", type="password", value=os.getenv("META_ACCESS_TOKEN", ""))

with st.form("brand_form"):
    col1, col2 = st.columns(2)
    with col1:
        brand_name = st.text_input("Your Brand Name", placeholder="e.g., Lumina Sleep")
    with col2:
        manual_override = st.text_input("Manual Competitor Page ID (Optional)", placeholder="e.g., 15087023444")

    product_desc = st.text_area(
        "Product Description & Positioning",
        placeholder="Organic magnesium night drink mix targeting professionals...",
    )
    submit_btn = st.form_submit_button("🚀 Run Ad Intelligence Pipeline")

if submit_btn:
    api_key = openai_input or os.getenv("OPENAI_API_KEY")
    meta_token = meta_input or os.getenv("META_ACCESS_TOKEN")

    if not api_key or not meta_token:
        st.error("Missing credentials. Please enter API keys in the sidebar or Streamlit Secrets.")
    elif not brand_name or not product_desc:
        st.error("Please fill out your brand name and product description.")
    else:
        os.environ["OPENAI_API_KEY"] = api_key
        
        with st.spinner("Analyzing competitor ad telemetry..."):
            overrides = [manual_override] if manual_override else None
            results_df = run_end_to_end_competitor_pipeline(
                brand_name=brand_name,
                product_description=product_desc,
                meta_access_token=meta_token,
                manual_overrides=overrides,
            )

        if results_df is not None and not results_df.empty:
            st.success("Analysis Complete!")
            st.dataframe(results_df, use_container_width=True)
        else:
            st.warning("No active ads retrieved for the specified competitor Page ID.")
