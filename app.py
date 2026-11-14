import os
import pandas as pd
import streamlit as st

# Automatically bridge Streamlit Secrets to OS environment variables
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

if "SOCIALCRAWL_API_KEY" in st.secrets:
    os.environ["SOCIALCRAWL_API_KEY"] = st.secrets["SOCIALCRAWL_API_KEY"]

from pipeline import run_end_to_end_competitor_pipeline

st.set_page_config(
    page_title="Competitor Ad Intelligence", layout="wide"
)

st.title("AI Competitor Ad Intelligence & Brief Generator")
st.markdown(
    "Enter your brand—Groq automatically identifies your top competitors, pulls their active ads via SocialCrawl, and generates creative briefs."
)

# Sidebar - Key Configuration
with st.sidebar:
    st.header("API Configurations")
    groq_input = st.text_input(
        "Groq API Key (Free)",
        type="password",
        value=os.getenv("GROQ_API_KEY", ""),
    )
    socialcrawl_input = st.text_input(
        "SocialCrawl API Key",
        type="password",
        value=os.getenv("SOCIALCRAWL_API_KEY", ""),
    )
    num_competitors = st.slider(
        "Auto-Discovered Competitors", min_value=1, max_value=5, value=3
    )

# Input Form
with st.form("brand_form"):
    col1, col2 = st.columns(2)
    with col1:
        brand_name = st.text_input(
            "Your Brand Name", placeholder="e.g., McDonald's"
        )
    with col2:
        manual_override = st.text_input(
            "Manual Competitor Override (Optional)",
            placeholder="Leave blank to auto-discover via Groq",
        )

    product_desc = st.text_area(
        "Product Description & Positioning",
        placeholder="Fast-food burger chain famous for Big Macs, fries, and value meals...",
    )
    submit_btn = st.form_submit_button("Discover Competitors & Generate Briefs")

if submit_btn:
    groq_key = groq_input or os.getenv("GROQ_API_KEY")
    socialcrawl_key = socialcrawl_input or os.getenv("SOCIALCRAWL_API_KEY")

    if not groq_key:
        st.error(
            "Missing credentials. Enter your Groq API key in the sidebar or Streamlit Secrets."
        )
    elif not brand_name or not product_desc:
        st.error("Please fill out your brand name and product description.")
    else:
        os.environ["GROQ_API_KEY"] = groq_key
        if socialcrawl_key:
            os.environ["SOCIALCRAWL_API_KEY"] = socialcrawl_key

        with st.spinner("Identifying competitors with Groq and scanning active ads..."):
            overrides = [manual_override.strip()] if manual_override.strip() else None
            results_df, discovered_competitors = run_end_to_end_competitor_pipeline(
                brand_name=brand_name,
                product_description=product_desc,
                socialcrawl_api_key=socialcrawl_key or "",
                manual_overrides=overrides,
                max_competitors=num_competitors,
            )

        if discovered_competitors:
            st.subheader("Targeted Competitors")
            comp_cols = st.columns(len(discovered_competitors))
            for idx, comp in enumerate(discovered_competitors):
                with comp_cols[idx]:
                    st.info(
                        f"**{comp.get('company_name')}**\n\n{comp.get('reason', '')}"
                    )

        if results_df is not None and not results_df.empty:
            st.success("Analysis Complete!")
            st.subheader("Generated Creative Briefs")

            st.dataframe(results_df, width="stretch")

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
                label="Download Briefs CSV",
                data=results_df.to_csv(index=False),
                file_name="competitor_briefs.csv",
                mime="text/csv",
            )
        else:
            st.warning("No ad results were generated. Please try again.")
