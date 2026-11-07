from datetime import datetime, timezone
import json
import os
import time
import pandas as pd
from pydantic import BaseModel
import requests
from openai import OpenAI


# Schemas
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


def discover_competitors(
    brand_name: str, product_description: str
) -> list[dict]:
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


class MetaAdLongevityEngine:

    def __init__(self, meta_access_token: str):
        self.meta_access_token = meta_access_token
        self.base_url = "https://graph.facebook.com/v19.0/ads_archive"

    def fetch_page_ads(
        self, page_id: str, country: str = "US", max_pages: int = 2
    ) -> list:
        params = {
            "access_token": self.meta_access_token,
            "search_page_ids": page_id,
            "ad_active_status": "ACTIVE",
            "ad_reached_countries": json.dumps([country]),
            "fields": (
                "id,ad_creation_time,ad_delivery_start_time,"
                "ad_creative_bodies,ad_creative_link_titles,page_id,page_name"
            ),
            "limit": 25,
        }
        all_ads, url, page_count = [], self.base_url, 0
        while url and page_count < max_pages:
            res = requests.get(
                url, params=params if url == self.base_url else None
            )
            if res.status_code != 200:
                print(f"Meta Graph API error ({res.status_code}): {res.text}")
                break
            data = res.json()
            all_ads.extend(data.get("data", []))
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
                    "page_name": ad.get("page_name", "Unknown Page"),
                    "days_active": days_active,
                    "tier": (
                        "Tier 1"
                        if days_active >= 45
                        else "Tier 2" if days_active >= 21 else "Tier 3"
                    ),
                    "headline": titles[0] if titles else "",
                    "primary_text": bodies[0] if bodies else "",
                }
            )
        return pd.DataFrame(processed)


def generate_brand_brief(ad_record: dict, brand_profile: str) -> dict:
    client = OpenAI()
    prompt = f"Deconstruct competitor ad and adapt for brand:\nAd: {ad_record}\nBrand: {brand_profile}"
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format=CreativeBrief,
    )
    return response.choices[0].message.parsed.model_dump()


def run_end_to_end_competitor_pipeline(
    brand_name: str,
    product_description: str,
    meta_access_token: str,
    manual_overrides: list[str] = None,
) -> pd.DataFrame:
    brand_profile = f"Brand: {brand_name}\nDescription: {product_description}"
    target_page_ids = manual_overrides or ["15087023444"]

    ad_engine = MetaAdLongevityEngine(meta_access_token=meta_access_token)
    all_scored = []
    for pid in target_page_ids:
        raw_ads = ad_engine.fetch_page_ads(page_id=pid, max_pages=2)
        if raw_ads:
            df = ad_engine.score_ads(raw_ads)
            if not df.empty:
                all_scored.append(df)

    if not all_scored:
        return pd.DataFrame()

    master_df = pd.concat(all_scored, ignore_index=True)
    top_ads = master_df.to_dict(orient="records")

    briefs = []
    for ad in top_ads[:3]:
        brief = generate_brand_brief(ad, brand_profile)
        briefs.append({**ad, **brief})

    return pd.DataFrame(briefs)
