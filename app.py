import os
import pandas as pd
import streamlit as st
from pipeline import run_end_to_end_competitor_pipeline

st.set_page_config(
    page_title="Competitor Ad Intelligence", page_icon="⚡", layout="wide"
)

st.title("⚡ AI Competitor Ad Intelligence & Brief Generator")
st.markdown(
    "Discover competitor ad strategies, score ad longevity, and generate custom creative briefs."
)

# Sidebar - API Keys & Settings
with st.sidebar:
    st.header("🔑 API Configurations")
    openai_key = st.text_input("OpenAI API Key", type="password")
    meta_token = st.text_input("Meta Graph Access Token", type="password")

# Form Inputs
with st.form("brand_form"):
    col1, col2 = st.columns(2)
    with col1:
        brand_name = st.text_input(
            "Your Brand Name", placeholder="e.g., Lumina Sleep"
        )
    with col2:
        manual_override = st.text_input(
            "Manual Competitor Domain (Optional)", placeholder="e.g., moonjuice.com"
        )

    product_desc = st.text_area(
        "Product Description & Positioning",
        placeholder="Organic magnesium night drink mix targeting professionals with insomnia...",
    )

    submit_btn = st.form_submit_button("🚀 Run Ad Intelligence Pipeline")

if submit_btn:
    if not openai_key or not meta_token:
        st.error("Please provide both OpenAI API Key and Meta Access Token.")
    elif not brand_name or not product_desc:
        st.error("Please fill out your brand name and product description.")
    else:
        os.environ["OPENAI_API_KEY"] = openai_key

        with st.spinner("Step 1/4: Discovering competitors with AI..."):
            # Call your unified pipeline function
            overrides = [manual_override] if manual_override else None
            
            # Execute pipeline
            run_end_to_end_competitor_pipeline(
                brand_name=brand_name,
                product_description=product_desc,
                meta_access_token=meta_token,
                manual_overrides=overrides,
            )

        st.success("Analysis Complete!")

        # Display results CSV if generated
        if os.path.exists("master_creative_execution_briefs.csv"):
            df = pd.read_csv("master_creative_execution_briefs.csv")
            st.subheader("Generated Creative Briefs")
            st.dataframe(df)

            st.download_button(
                label="📥 Download Briefs CSV",
                data=df.to_csv(index=False),
                file_name="competitor_briefs.csv",
                mime="text/csv",
            )
