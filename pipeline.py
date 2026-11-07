from datetime import datetime, timezone
import json
import os
import time
import pandas as pd
from pydantic import BaseModel
import requests
from groq import Groq


# ==========================================
# 1. STRUCTURED SCHEMAS
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
# 2. SOCIALCRAWL AD ENGINE
# ==========================================
class SocialCrawlAdEngine:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.socialcrawl.dev/v1/ads/search"

    def fetch_page_ads(
        self, search_term: str, country: str = "US", max_pages: int = 1
    ) -> list:
        # SocialCrawl accepts x-api-key or Bearer token header
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        params = {
            "query": search_term,
            "country": country,
            "status": "ACTIVE",
            "limit": 25,
        }

        try:
            res = requests.get(
                self.base_url, headers=headers, params=params, timeout=10
            )

            # Fallback to realistic mock data if token is invalid, empty, or out of credits
            if res.status_code != 200:
                print(
                    f"SocialCrawl API ({res.status_code}). Bypassing with mock payload for testing."
                )
                display_name = search_term.title()
                return [
                    {
                        "id": "sc_mock_101",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2024-01-15T00:00:00+0000",
                        "headline": "Get 2 Whoppers for $10 This Weekend Only!",
                        "primary_text": "Tired of paying full price for lunch? Claim your exclusive app coupon and get 2 iconic Whoppers for just $10.",
                    },
                    {
                        "id": "sc_mock_102",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2023-11-01T00:00:00+0000",
                        "headline": "The Flame-Grilled Difference You Can Taste",
                        "primary_text": "We don't fry, we flame-grill. Taste the real smokey flavor that has kept burger lovers coming back for 70 years.",
                    },
                    {
                        "id": "sc_mock_103",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2024-03-01T00:00:00+0000",
                        "headline": "Upgrade Your Meals with Double Bacon & Cheese",
                        "primary_text": "Why settle for a plain burger when you can double the flavor? Order online now and get free delivery on your first order.",
                    },
                ]

            data = res.json()
            return data.get("ads", []) or data.get("data", [])

        except Exception as e:
            print(f"SocialCrawl Connection Error: {e}")
            display_name = search_term.title()
            return [
                {
                    "id": "sc_mock_101",
                    "page_name": display_name,
                    "ad_delivery_start_time": "2024-01-15T00:00:00+0000",
                    "headline": "Get 2 Whoppers for $10 This Weekend Only!",
                    "primary_text": "Tired of paying full price for lunch? Claim your exclusive app coupon and get 2 iconic Whoppers for just $10.",
                },
                {
                    "id": "sc_mock_102",
                    "page_name": display_name,
                    "ad_delivery_start_time": "2023-11-01T00:00:00+0000",
                    "headline": "The Flame-Grilled Difference You Can Taste",
                    "primary_text": "We don't fry, we flame-grill. Taste the real smokey flavor that has kept burger lovers coming back for 70 years.",
                },
            ]

    def score_ads(self, ads: list) -> pd.DataFrame:
        processed, now = [], datetime.now(timezone.utc)
        for ad in ads:
            start_str = ad.get("ad_delivery_start_time") or ad.get(
                "first_shown_time"
            )
            if not start_str:
                continue

            days_active = (
                now - datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            ).days
            processed.append(
                {
                    "ad_id": ad.get("id") or ad.get("ad_id"),
                    "page_name": ad.get("page_name", "Unknown Competitor"),
                    "days_active": max(days_active, 1),
                    "tier": (
                        "Tier 1 (Winner)"
                        if days_active >= 45
                        else "Tier 2 (Solid)" if days_active >= 21 else "Tier 3 (New)"
                    ),
                    "headline": ad.get("headline", ""),
                    "primary_text": ad.get("primary_text", ""),
                }
            )
        df = pd.DataFrame(processed)
        if not df.empty:
            df = df.sort_values(by="days_active", ascending=False).reset_index(
                drop=True
            )
        return df


# ==========================================
# 3. BRIEF GENERATION MODULE (GROQ)
# ==========================================
def generate_brand_brief(ad_record: dict, brand_profile: str) -> dict:
    groq_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=groq_key)

    system_prompt = (
        "You are an expert direct-response creative director. "
        "Deconstruct winning competitor ad hooks and adapt them into custom creative briefs for the target brand."
    )
    user_prompt = f"COMPETITOR WINNING AD:\nCompetitor: {ad_record.get('page_name')}\nDays Active: {ad_record.get('days_active')}\nHeadline: {ad_record.get('headline')}\nPrimary Copy: {ad_record.get('primary_text')}\n\nMY BRAND PROFILE:\n{brand_profile}\n\nINSTRUCTIONS:\nDeconstruct and return a single valid JSON object with exact keys: extracted_hook, hook_type, emotional_trigger, adapted_hook_1, adapted_hook_2, adapted_hook_3, primary_text_draft, visual_execution_idea."

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


# ==========================================
# 4. MASTER EXECUTION PIPELINE
# ==========================================
def run_end_to_end_competitor_pipeline(
    brand_name: str,
    product_description: str,
    socialcrawl_api_key: str = "",
    manual_overrides: list[str] = None,
) -> pd.DataFrame:
    brand_profile = f"Brand: {brand_name}\nDescription: {product_description}"
    target_inputs = manual_overrides or ["burgerking"]

    ad_engine = SocialCrawlAdEngine(api_key=socialcrawl_api_key)
    all_scored = []

    for target in target_inputs:
        raw_ads = ad_engine.fetch_page_ads(search_term=target)
        if raw_ads:
            df = ad_engine.score_ads(raw_ads)
            if not df.empty:
                all_scored.append(df)

    if not all_scored:
        return pd.DataFrame()

    master_df = pd.concat(all_scored, ignore_index=True)
    master_df = master_df.sort_values(
        by="days_active", ascending=False
    ).reset_index(drop=True)

    top_ads = master_df.to_dict(orient="records")

    briefs = []
    for ad in top_ads[:3]:
        brief = generate_brand_brief(ad, brand_profile)
        briefs.append({**ad, **brief})

    results_df = pd.DataFrame(briefs)
    results_df.to_csv("master_creative_execution_briefs.csv", index=False)
    return results_df
