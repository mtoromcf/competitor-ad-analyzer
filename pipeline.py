from datetime import datetime, timezone
import json
import os
import time
import pandas as pd
from pydantic import BaseModel
import requests
from openai import OpenAI


# ==========================================
# 1. STRUCTURED OUTPUT SCHEMAS
# ==========================================
class CompetitorItem(BaseModel):
    company_name: str
    website_domain: str
    reason: str


class CompetitorDiscoveryResult(BaseModel):
    suggested_competitors: list[CompetitorItem]


class CreativeBrief(BaseModel):
    extracted_hook: str
    hook_type: str
    emotional_trigger: str
    adapted_hook_1: str
    adapted_hook_2: str
    adapted_hook_3: str
    primary_text_draft: str
    visual_execution_idea: str


# ==========================================
# 2. COMPETITOR DISCOVERY MODULE
# ==========================================
def discover_competitors(brand_name: str, product_description: str) -> list[dict]:
    client = OpenAI()
    system_prompt = (
        "Identify 3-5 direct competitors actively running paid Meta ads."
    )
    user_prompt = f"Brand: {brand_name}\nDescription: {product_description}"
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=CompetitorDiscoveryResult,
        )
        return [
            c.model_dump()
            for c in response.choices[0].message.parsed.suggested_competitors
        ]
    except Exception as e:
        print(f"Competitor discovery error: {e}")
        return []


# ==========================================
# 3. META AD TELEMETRY ENGINE
# ==========================================
class MetaAdLongevityEngine:

    def __init__(self, meta_access_token: str):
        self.meta_access_token = meta_access_token
        self.base_url = "https://graph.facebook.com/v19.0/ads_archive"

    def fetch_page_ads(
        self, target_input: str, country: str = "US", max_pages: int = 2
    ) -> list:
        """Fetches active ads by Page ID or fallback search terms."""
        params = {
            "access_token": self.meta_access_token,
            "ad_active_status": "ACTIVE",
            "ad_reached_countries": json.dumps([country]),
            "fields": (
                "id,ad_creation_time,ad_delivery_start_time,"
                "ad_creative_bodies,ad_creative_link_titles,page_id,page_name"
            ),
            "limit": 25,
        }

        # Use search_page_ids for numeric IDs, search_terms for brand names
        if target_input.isdigit():
            params["search_page_ids"] = target_input
        else:
            params["search_terms"] = target_input

        all_ads, url, page_count = [], self.base_url, 0
        while url and page_count < max_pages:
            res = requests.get(
                url, params=params if url == self.base_url else None
            )
            if res.status_code != 200:
                print(f"Meta API Error ({res.status_code}): {res.text}")
                break
            data = res.json()
            ads = data.get("data", [])
            all_ads.extend(ads)
            url = data.get("paging", {}).get("next")
            page_count += 1
            time.sleep(0.4)
            
        return all_ads

    def score_ads(self, ads: list) -> pd.DataFrame:
        processed, now = [], datetime.now(timezone.utc)
        for ad in ads:
            start_str = ad.get("ad_delivery_start_time") or ad.get(
                "ad_creation_time"
            )
            if not start_str:
                continue
            days_active = (
                now - datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            ).days
            bodies, titles = ad.get("ad_creative_bodies", []), ad.get(
                "ad_creative_link_titles", []
            )
            processed.append(
                {
                    "ad_id": ad.get("id"),
                    "page_name": ad.get("page_name", "Unknown Competitor"),
                    "days_active": days_active,
                    "tier": (
                        "Tier 1 (Winner)"
                        if days_active >= 45
                        else "Tier 2 (Solid)" if days_active >= 21 else "Tier 3 (New)"
                    ),
                    "headline": titles[0] if titles else "",
                    "primary_text": bodies[0] if bodies else "",
                }
            )
        df = pd.DataFrame(processed)
        if not df.empty:
            df = df.sort_values(by="days_active", ascending=False).reset_index(drop=True)
        return df


# ==========================================
# 4. OPENAI BRIEF DECONSTRUCTION
# ==========================================
def generate_brand_brief(ad_record: dict, brand_profile: str) -> dict:
    client = OpenAI()
    system_prompt = (
        "You are an expert direct-response creative director. "
        "Deconstruct winning competitor ad hooks and adapt them into custom creative briefs for the target brand."
    )
    user_prompt = f"""
--- COMPETITOR WINNING AD ---
Competitor: {ad_record.get('page_name')}
Days Active: {ad_record.get('days_active')} days
Headline: {ad_record.get('headline')}
Primary Copy: {ad_record.get('primary_text')}

--- MY BRAND PROFILE ---
{brand_profile}

--- INSTRUCTIONS ---
Extract the hook and adapt 3 variations, body text, and visual directions for MY BRAND.
"""

    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=CreativeBrief,
    )
    return response.choices[0].message.parsed.model_dump()


# ==========================================
# 5. MASTER EXECUTION PIPELINE
# ==========================================
def run_end_to_end_competitor_pipeline(
    brand_name: str,
    product_description: str,
    meta_access_token: str,
    manual_overrides: list[str] = None,
) -> pd.DataFrame:
    brand_profile = f"Brand: {brand_name}\nDescription: {product_description}"
    target_inputs = manual_overrides or ["burger king"]

    ad_engine = MetaAdLongevityEngine(meta_access_token=meta_access_token)
    all_scored = []

    for target in target_inputs:
        raw_ads = ad_engine.fetch_page_ads(target_input=target, max_pages=2)
        if raw_ads:
            df = ad_engine.score_ads(raw_ads)
            if not df.empty:
                all_scored.append(df)

    if not all_scored:
        return pd.DataFrame()

    master_df = pd.concat(all_scored, ignore_index=True)
    master_df = master_df.sort_values(by="days_active", ascending=False).reset_index(drop=True)

    # Use all retrieved ads sorted by longevity
    top_ads = master_df.to_dict(orient="records")

    briefs = []
    # Deconstruct top 3 longest-running ads
    for ad in top_ads[:3]:
        brief = generate_brand_brief(ad, brand_profile)
        briefs.append({**ad, **brief})

    results_df = pd.DataFrame(briefs)
    results_df.to_csv("master_creative_execution_briefs.csv", index=False)
    return results_df
