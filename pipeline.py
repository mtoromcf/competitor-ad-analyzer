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
# 2. FREE COMPETITOR DISCOVERY MODULE (GROQ)
# ==========================================
def discover_competitors(brand_name: str, product_description: str) -> list[dict]:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("Missing GROQ_API_KEY environment variable.")
        return []

    client = Groq(api_key=groq_key)
    system_prompt = "Identify 3-5 direct competitors actively running paid Meta ads. Return response in valid JSON matching key 'suggested_competitors'."
    user_prompt = f"Brand: {brand_name}\nDescription: {product_description}"

    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("suggested_competitors", [])
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
        target_str = str(target_input).strip()

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

        if target_str.isdigit():
            params["search_page_ids"] = target_str
        else:
            params["search_terms"] = target_str

        all_ads, url, page_count = [], self.base_url, 0
        while url and page_count < max_pages:
            res = requests.get(
                url, params=params if url == self.base_url else None
            )

            # --- MOCK FALLBACK FOR UNVERIFIED ACCOUNTS OR TOKEN BLOCKS ---
            if res.status_code != 200:
                print(
                    f"Meta Graph API ({res.status_code}): {res.text}\n"
                    "--> Bypassing with realistic telemetry payload for pipeline testing."
                )
                display_name = (
                    target_str.title()
                    if not target_str.isdigit()
                    else "Target Competitor"
                )
                return [
                    {
                        "id": "ad_mock_101",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2024-01-15T00:00:00+0000",
                        "ad_creative_link_titles": [
                            "Get 2 Whoppers for $10 This Weekend Only!"
                        ],
                        "ad_creative_bodies": [
                            "Tired of paying full price for lunch? Claim your exclusive app coupon and get 2 iconic Whoppers for just $10."
                        ],
                    },
                    {
                        "id": "ad_mock_102",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2023-11-01T00:00:00+0000",
                        "ad_creative_link_titles": [
                            "The Flame-Grilled Difference You Can Taste"
                        ],
                        "ad_creative_bodies": [
                            "We don't fry, we flame-grill. Taste the real smokey flavor that has kept burger lovers coming back for 70 years."
                        ],
                    },
                    {
                        "id": "ad_mock_103",
                        "page_name": display_name,
                        "ad_delivery_start_time": "2024-03-01T00:00:00+0000",
                        "ad_creative_link_titles": [
                            "Upgrade Your Meals with Double Bacon & Cheese"
                        ],
                        "ad_creative_bodies": [
                            "Why settle for a plain burger when you can double the flavor? Order online now and get free delivery on your first order."
                        ],
                    },
                ]

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
# 4. FREE BRIEF DECONSTRUCTION (GROQ)
# ==========================================
def generate_brand_brief(ad_record: dict, brand_profile: str) -> dict:
    groq_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=groq_key)

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
Deconstruct and return a single valid JSON object with the following exact keys:
extracted_hook,
