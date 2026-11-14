import importlib.util
import os
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Competitor Ad Intelligence", layout="wide"
)

# Automatically bridge Streamlit Secrets to OS environment variables
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

if "SOCIALCRAWL_API_KEY" in st.secrets:
    os.environ["SOCIALCRAWL_API_KEY"] = st.secrets["SOCIALCRAWL_API_KEY"]


def load_pipeline_function():
    pipeline_path = Path(__file__).parent / "pipeline.py"
    spec = importlib.util.spec_from_file_location("ad_pipeline_mod", pipeline_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_end_to_end_competitor_pipeline


run_end_to_end_competitor_pipeline = load_pipeline_function()


def render_telemetry_charts(master_df: pd.DataFrame):
    """Renders range bar, donut/pie, and tier breakdown charts across all scanned ads."""
    st.subheader("Ad Telemetry & Market Overview")

    # Summary KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Active Ads Scanned", len(master_df))
    k2.metric(
        "Tier 1 Winners (45+ Days)",
        int((master_df["days_active"] >= 45).sum()),
    )
    k3.metric("Median Run Length", f"{int(master_df['days_active'].median())} days")
    k4.metric("Max Ad Longevity", f"{int(master_df['days_active'].max())} days")

    chart_col1, chart_col2 = st.columns([3, 2])

    # 1. Longevity Range Bar + Individual Ad Scatter Points
    with chart_col1:
        st.markdown("**Ad Longevity Range Bar (Days Active by Competitor)**")
        range_df = (
            master_df.groupby("page_name", as_index=False)
            .agg(
                min_days=("days_active", "min"),
                median_days=("days_active", "median"),
                max_days=("days_active", "max"),
                ad_count=("days_active", "count"),
            )
        )

        bar_layer = (
            alt.Chart(range_df)
            .mark_bar(size=14, cornerRadius=7, opacity=0.45, color="#3b82f6")
            .encode(
                x=alt.X("min_days:Q", title="Days Active"),
                x2="max_days:Q",
                y=alt.Y("page_name:N", title="Competitor", sort="-x"),
                tooltip=[
                    alt.Tooltip("page_name:N", title="Competitor"),
                    alt.Tooltip("ad_count:Q", title="Active Ads"),
                    alt.Tooltip("min_days:Q", title="Min Days"),
                    alt.Tooltip("median_days:Q", title="Median Days"),
                    alt.Tooltip("max_days:Q", title="Max Days"),
                ],
            )
        )

        points_layer = (
            alt.Chart(master_df)
            .mark_circle(size=55, opacity=0.85)
            .encode(
                x=alt.X("days_active:Q", title="Days Active"),
                y=alt.Y("page_name:N", sort="-x"),
                color=alt.Color(
                    "tier:N",
                    title="Longevity Tier",
                    scale=alt.Scale(
                        domain=[
                            "Tier 1 (Winner)",
                            "Tier 2 (Solid)",
                            "Tier 3 (New)",
                        ],
                        range=["#10b981", "#f59e0b", "#6366f1"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("page_name:N", title="Competitor"),
                    alt.Tooltip("days_active:Q", title="Days Active"),
                    alt.Tooltip("tier:N", title="Tier"),
                    alt.Tooltip("media_type:N", title="Format"),
                    alt.Tooltip("headline:N", title="Headline"),
                ],
            )
        )

        st.altair_chart(
            (bar_layer + points_layer).properties(height=260),
            use_container_width=True,
        )

    # 2. Creative Format Mix (Donut / Pie Chart)
    with chart_col2:
        st.markdown("**Creative Format Distribution**")
        format_df = (
            master_df["media_type"]
            .fillna("Text / Other")
            .value_counts()
            .reset_index()
        )
        format_df.columns = ["Format", "Count"]

        donut_chart = (
            alt.Chart(format_df)
            .mark_arc(innerRadius=55, outerRadius=100)
            .encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color(
                    "Format:N",
                    scale=alt.Scale(
                        range=["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Format:N", title="Ad Format"),
                    alt.Tooltip("Count:Q", title="Ad Count"),
                ],
            )
            .properties(height=260)
        )
        st.altair_chart(donut_chart, use_container_width=True)

    # Row 2: Tier Stacked Bar + CTA & Platform Breakdown
    sub_col1, sub_col2, sub_col3 = st.columns(3)

    with sub_col1:
        st.markdown("**Performance Tiers by Competitor**")
        tier_df = (
            master_df.groupby(["page_name", "tier"], as_index=False)
            .size()
            .rename(columns={"size": "Count"})
        )
        tier_chart = (
            alt.Chart(tier_df)
            .mark_bar()
            .encode(
                x=alt.X("page_name:N", title="Competitor"),
                y=alt.Y("Count:Q", title="Number of Ads"),
                color=alt.Color(
                    "tier:N",
                    title="Tier",
                    scale=alt.Scale(
                        domain=[
                            "Tier 1 (Winner)",
                            "Tier 2 (Solid)",
                            "Tier 3 (New)",
                        ],
                        range=["#10b981", "#f59e0b", "#6366f1"],
                    ),
                ),
                tooltip=["page_name", "tier", "Count"],
            )
            .properties(height=230)
        )
        st.altair_chart(tier_chart, use_container_width=True)

    with sub_col2:
        st.markdown("**Call-to-Action (CTA) Breakdown**")
        cta_series = (
            master_df["cta_text"]
            .fillna("")
            .replace("", "No CTA / Brand")
            .value_counts()
            .head(6)
            .reset_index()
        )
        cta_series.columns = ["CTA", "Count"]
        cta_pie = (
            alt.Chart(cta_series)
            .mark_arc(innerRadius=45, outerRadius=85)
            .encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("CTA:N", title="CTA Button"),
                tooltip=["CTA", "Count"],
            )
            .properties(height=230)
        )
        st.altair_chart(cta_pie, use_container_width=True)

    with sub_col3:
        st.markdown("**Publisher Platform Reach**")
        plat_series = (
            master_df["platforms"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
            .replace("", "Unspecified")
            .value_counts()
            .reset_index()
        )
        plat_series.columns = ["Platform", "Count"]
        plat_bar = (
            alt.Chart(plat_series)
            .mark_bar(cornerRadiusEnd=4, color="#8b5cf6")
            .encode(
                x=alt.X("Count:Q", title="Ads Running"),
                y=alt.Y("Platform:N", sort="-x", title=""),
                tooltip=["Platform", "Count"],
            )
            .properties(height=230)
        )
        st.altair_chart(plat_bar, use_container_width=True)


st.title("Competitor ad analyzer")
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
        "Product Description",
        placeholder="Fast-food burger chain famous for Big Macs, fries, and value meals...",
    )
    submit_btn = st.form_submit_button("Generate Briefs")

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
            (
                results_df,
                master_df,
                discovered_competitors,
                diagnostics,
            ) = run_end_to_end_competitor_pipeline(
                brand_name=brand_name,
                product_description=product_desc,
                socialcrawl_api_key=socialcrawl_key or "",
                manual_overrides=overrides,
                max_competitors=num_competitors,
            )

        credits_left = diagnostics.get("credits_remaining")
        status_logs = diagnostics.get("status_logs", [])
        if status_logs:
            credit_note = (
                f" | SocialCrawl Credits Remaining: {credits_left}"
                if credits_left is not None
                else ""
            )
            st.caption(" • ".join(status_logs) + credit_note)

        if discovered_competitors:
            st.subheader("Targeted Competitors")
            comp_cols = st.columns(len(discovered_competitors))
            for idx, comp in enumerate(discovered_competitors):
                with comp_cols[idx]:
                    st.info(
                        f"**{comp.get('company_name')}**\n\n{comp.get('reason', '')}"
                    )

        if master_df is not None and not master_df.empty:
            st.divider()
            render_telemetry_charts(master_df)
            st.divider()

        if results_df is not None and not results_df.empty:
            st.success("Analysis Complete!")
            st.subheader("Generated Creative Briefs")

            display_df = results_df.drop(
                columns=["image_urls", "video_urls"], errors="ignore"
            )
            st.dataframe(display_df, width="stretch")

            for idx, row in results_df.iterrows():
                media_label = row.get("media_type", "Ad")
                with st.expander(
                    f"Brief #{idx+1}: {row.get('page_name', 'Competitor')} — {media_label} (Active {row.get('days_active', 0)} Days)",
                    expanded=(idx == 0),
                ):
                    media_col, brief_col = st.columns([1, 2])

                    with media_col:
                        st.markdown("**Original Ad Creative**")
                        video_urls = row.get("video_urls") or []
                        image_urls = row.get("image_urls") or []

                        if video_urls:
                            st.video(video_urls[0])
                        elif image_urls:
                            st.image(image_urls[0], use_container_width=True)
                            if len(image_urls) > 1:
                                extra_cols = st.columns(min(len(image_urls) - 1, 3))
                                for c_idx, img_url in enumerate(image_urls[1:4]):
                                    with extra_cols[c_idx]:
                                        st.image(img_url, use_container_width=True)
                        else:
                            st.caption("No direct image or video URL exposed for this ad.")

                        if row.get("headline"):
                            st.markdown(f"**Headline:** {row.get('headline')}")
                        if row.get("primary_text"):
                            st.caption(row.get("primary_text"))

                        meta_bits = []
                        if row.get("cta_text"):
                            meta_bits.append(f"**CTA:** {row.get('cta_text')}")
                        if row.get("platforms"):
                            meta_bits.append(f"**Platforms:** {row.get('platforms')}")
                        if meta_bits:
                            st.markdown(" • ".join(meta_bits))

                        if row.get("link_url"):
                            st.markdown(f"[View Destination Landing Page]({row.get('link_url')})")

                    with brief_col:
                        st.markdown(f"**Hook Strategy:** {row.get('hook_type', 'N/A')}")
                        st.markdown(f"**Emotional Trigger:** {row.get('emotional_trigger', 'N/A')}")
                        st.markdown(f"**Original Competitor Hook:** {row.get('extracted_hook', 'N/A')}")
                        st.markdown("**Adapted Hooks for Your Brand:**")
                        st.markdown(f"- **Option 1:** {row.get('adapted_hook_1')}")
                        st.markdown(f"- **Option 2:** {row.get('adapted_hook_2')}")
                        st.markdown(f"- **Option 3:** {row.get('adapted_hook_3')}")
                        st.markdown("**Primary Ad Copy Draft:**")
                        st.write(row.get("primary_text_draft", ""))
                        st.info(f"**Visual Execution Plan:** {row.get('visual_execution_idea')}")

            st.download_button(
                label="Download Briefs CSV",
                data=display_df.to_csv(index=False),
                file_name="competitor_briefs.csv",
                mime="text/csv",
            )
        else:
            st.warning("No ad results were generated. Please try again.")
