import os
import pandas as pd
import streamlit as st

# Automatically bridge Streamlit Secrets to OS environment variables
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

if "META_ACCESS_TOKEN" in st.secrets:
    os.environ["META_ACCESS_TOKEN"] = st.secrets["META_ACCESS_TOKEN"]

from pipeline import run_end_to_end_competitor_pipeline

st.set_page_config(
    page_title="Competitor Ad Intelligence", page_icon="⚡", layout="wide"
)

st.title("⚡ AI Competitor Ad Intelligence & Brief Generator")
st.markdown(
    "Discover competitor ad strategies, score ad longevity, and generate tailored creative briefs."
)

# Sidebar - Key Configuration
with st.sidebar:
    st.header("🔑 API Configurations")
    groq_input = st.text_input(
        "Groq API Key (Free)",
        type="password",
        value=os.getenv("GROQ_API_KEY", ""),
    )
    meta_input = st.text_input(
        "Meta Graph Access Token",
        type="password",
        value=os.getenv("META_ACCESS_TOKEN", ""),
    )

# Input Form
with st.form("brand_form"):
    col1, col2 = st.columns(2)
    with col1:
        brand_name = st.text_input(
            "Your Brand Name", placeholder="e.g., Lumina Sleep"
        )
    with col2:
        manual_override = st.text_input(
            "Competitor Page ID or Brand Name",
            placeholder="e.g., 20000000000 or burgerking",
        )

    product_desc = st.text_area(
        "Product Description & Positioning",
        placeholder="Organic magnesium night drink mix targeting busy professionals...",
    )
    submit_btn = st.form_submit_button("🚀 Run Ad Intelligence Pipeline")

if submit_btn:
    groq_key = groq_input or os.getenv("GROQ_API_KEY")
    meta_token = meta_input or os.getenv("META_ACCESS_TOKEN")

    if not groq_key or not meta_token:
        st.error(
            "Missing credentials. Enter your API keys in the sidebar or Streamlit Secrets."
        )
    elif not brand_name or not product_desc:
        st.error("Please fill out your brand name and product description.")
    else:
        os.environ["GROQ_API_KEY"] = groq_key
        os.environ["META_ACCESS_TOKEN"] = meta_token

        with st.spinner("Fetching Meta ad telemetry and generating briefs with Groq..."):
            overrides = [manual_override] if manual_override else None
            results_df = run_end_to_end_competitor_pipeline(
                brand_name=brand_name,
                product_description=product_desc,
                meta_access_token=meta_token,
                manual_overrides=overrides,
            )

        if results_df is not None and not results_df.empty:
            st.success("Analysis Complete!")
            st.subheader("📋 Generated Creative Briefs")

            # Dataframe display
            st.dataframe(results_df, use_container_width=True)

            # Interactive expanders per brief
            for idx, row in results_df.iterrows():
                with st.expander(
                    f"Brief #{idx+1}: {row.get('page_name', 'Competitor')} (Active {row.get('days_active', 0)} Days)"
                ):
                    st.markdown(f"**Hook Strategy:** {row.get('hook_type', 'N/A')}")
                    st.markdown(f"**Original Competitor Hook:** {row.get('extracted_hook', 'N/A')}")
                    st.markdown("**Adapted Hooks for Your Brand:**")
                    st.markdown(f"- **Option 1:** {row.get('adapted_hook_1')}")
                    st.markdown(f"- **Option 2:** {row.get('adapted_hook_2')}")
                    st.markdown(f"- **Option 3:** {row.get('adapted_hook_3')}")
                    st.info(f"**Visual Execution Plan:** {row.get('visual_execution_idea')}")

            st.download_button(
                label="📥 Download Briefs CSV",
                data=results_df.to_csv(index=False),
                file_name="competitor_briefs.csv",
                mime="text/csv",
            )
        else:
            st.warning(
                "No active ads retrieved for the specified target. Verify your Meta Access Token permissions or try a brand name keyword like 'burgerking'."
            )
