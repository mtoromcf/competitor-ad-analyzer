from datetime import datetime, timezone
import json
import os
import pandas as pd
from pydantic import BaseModel
import requests
from groq import Groq


# ==========================================
# 1. STRUCTURED SCHEMAS
# ==========================================
class CompetitorItem(BaseModel):
    company_name: str
    search_keyword: str
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
# 2. GROQ COMPETITOR DISCOVERY ENGINE
# ==========================================
def discover_competitors_with_groq(
    brand_name: str, product_description: str, max_competitors: int = 3
) -> list[dict]:
    """Uses Groq to automatically identify top direct competitors for a given brand."""
    groq_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=groq_key)

    system_prompt = (
        "You are a senior market intelligence strategist. Given a brand name and product description, "
        "identify its top direct competitors that actively run paid social ads on Meta (Facebook/Instagram)."
    )
    user_prompt = (
        f"TARGET BRAND: {brand_name}\n"
        f"PRODUCT / POSITIONING: {product_description}\n\n"
        f"INSTRUCTIONS:\n"
        f"Identify up to {max_competitors} top direct competitors (for example, if Target Brand is McDonald's, "
        f"return Burger King, Wendy's, Taco Bell).\n"
        f"Return ONLY a valid JSON object with exact key 'suggested_competitors', containing a list of objects "
        f"with exact keys: 'company_name' (official brand name), 'search_keyword' (clean brand name to search in Meta Ad Library), "
        f"and 'reason' (1-sentence explanation of why they compete)."
    )

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        competitors = parsed.get("suggested_competitors", [])
        return competitors[:max_competitors]
    except Exception as e:
        print(f"Groq Competitor Discovery Error: {e}")
        return []


# ==========================================
# 3. SOCIALCRAWL AD ENGINE
# ==========================================
class SocialCrawlAdEngine:

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.base_url = "https://www.socialcrawl.dev/v1/facebook/adlibrary/search/ads"

    def fetch_page_ads(
        self, search_term: str, country: str = "US", max_pages: int = 1
    ) -> list:
        if not self.api_key:
            print("No SocialCrawl API key provided. Using mock fallback.")
            return self._get_mock_ads(search_term)

        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }
        params = {
            "query": search_term,
            "country": country,
            "status": "ACTIVE",
        }

        try:
            res = requests.get(
                self.base_url, headers=headers, params=params, timeout=20
            )

            if res.status_code != 200:
                print(
                    f"SocialCrawl API Error ({res.status_code}): {res.text}\n"
                    "--> Bypassing with mock payload."
                )
                return self._get_mock_ads(search_term)

            payload = res.json()
            if not payload.get("success", True):
                print(f"SocialCrawl Envelope Error: {payload}")
                return self._get_mock_ads(search_term)

            data_block = payload.get("data", {})
            items = (
                data_block.get("items", [])
                if isinstance(data_block, dict)
                else data_block
            )

            if not items:
                print(f"SocialCrawl returned 0 ads for '{search_term}'. Using mock fallback.")
                return self._get_mock_ads(search_term)

            print(
                f"SocialCrawl LIVE HIT for '{search_term}': Fetched {len(items)} ads! "
                f"(Credits remaining: {payload.get('credits_remaining', 'N/A')})"
            )
            return items

        except Exception as e:
            print(f"SocialCrawl Connection Exception: {e}")
            return self._get_mock_ads(search_term)

    def _get_mock_ads(self, search_term: str) -> list:
        display_name = search_term.title()
        return [
            {
                "id": "sc_mock_101",
                "page_name": display_name,
                "ad_delivery_start_time": "2024-01-15T00:00:00+00:00",
                "headline": f"Exclusive Limited-Time Offer from {display_name}!",
                "primary_text": f"Tired of overpaying? Claim your exclusive app deal from {display_name} this weekend only.",
            },
            {
                "id": "sc_mock_102",
                "page_name": display_name,
                "ad_delivery_start_time": "2023-11-01T00:00:00+00:00",
                "headline": f"Why Millions Choose {display_name} Every Day",
                "primary_text": f"Discover the signature quality and unbeatable value that has kept {display_name} fans coming back.",
            },
        ]

    def _parse_start_date(self, raw_date) -> datetime:
        now = datetime.now(timezone.utc)
        if not raw_date:
            return now
        try:
            if isinstance(raw_date, (int, float)):
                return datetime.fromtimestamp(raw_date, tz=timezone.utc)
            clean_str = str(raw_date).replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return now

    def score_ads(self, ads: list) -> pd.DataFrame:
        processed, now = [], datetime.now(timezone.utc)
        for ad in ads:
            snapshot = ad.get("snapshot") if isinstance(ad.get("snapshot"), dict) else {}

            start_raw = (
                ad.get("start_date")
                or ad.get("ad_delivery_start_time")
                or ad.get("created_at")
                or ad.get("first_shown_time")
            )
            start_dt = self._parse_start_date(start_raw)
            days_active = max((now - start_dt).days, 1)

            page_name = (
                ad.get("page_name")
                or ad.get("advertiser_name")
                or snapshot.get("page_name")
                or "Unknown Competitor"
            )

            headline = (
                ad.get("headline")
                or ad.get("title")
                or snapshot.get("title")
                or (
                    ad.get("ad_creative_link_titles")[0]
                    if isinstance(ad.get("ad_creative_link_titles"), list)
                    and ad.get("ad_creative_link_titles")
                    else ""
                )
            )

            body_obj = snapshot.get("body") if isinstance(snapshot.get("body"), dict) else {}
            primary_text = (
                ad.get("primary_text")
                or ad.get("body")
                or ad.get("text")
                or body_obj.get("text")
                or (
                    ad.get("ad_creative_bodies")[0]
                    if isinstance(ad.get("ad_creative_bodies"), list)
                    and ad.get("ad_creative_bodies")
                    else ""
                )
            )

            if not headline and not primary_text:
                continue

            processed.append(
                {
                    "ad_id": str(ad.get("id") or ad.get("ad_archive_id") or ad.get("ad_id") or "unknown"),
                    "page_name": page_name,
                    "days_active": days_active,
                    "tier": (
                        "Tier 1 (Winner)"
                        if days_active >= 45
                        else "Tier 2 (Solid)" if days_active >= 21 else "Tier 3 (New)"
                    ),
                    "headline": str(headline),
                    "primary_text": str(primary_text),
                }
            )

        df = pd.DataFrame(processed)
        if not df.empty:
            df = df.sort_values(by="days_active", ascending=False).reset_index(
                drop=True
            )
        return df


# ==========================================
# 4. BRIEF GENERATION MODULE (GROQ)
# ==========================================
def generate_brand_brief(ad_record: dict, brand_profile: str) -> dict:
    groq_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=groq_key)

    system_prompt = (
        "You are an expert direct-response creative director. "
        "Deconstruct winning competitor ad hooks and adapt them into custom creative briefs for the target brand."
    )
    user_prompt = (
        f"COMPETITOR WINNING AD:\n"
        f"Competitor: {ad_record.get('page_name')}\n"
        f"Days Active: {ad_record.get('days_active')}\n"
        f"Headline: {ad_record.get('headline')}\n"
        f"Primary Copy: {ad_record.get('primary_text')}\n\n"
        f"MY BRAND PROFILE:\n{brand_profile}\n\n"
        f"INSTRUCTIONS:\n"
        f"Deconstruct and return a single valid JSON object with exact keys: "
        f"extracted_hook, hook_type, emotional_trigger, adapted_hook_1, adapted_hook_2, "
        f"adapted_hook_3, primary_text_draft, visual_execution_idea."
    )

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
# 5. MASTER EXECUTION PIPELINE
# ==========================================
def run_end_to_end_competitor_pipeline(
    brand_name: str,
    product_description: str,
    socialcrawl_api_key: str = "",
    manual_overrides: list[str] = None,
    max_competitors: int = 3,
) -> tuple[pd.DataFrame, list[dict]]:
    brand_profile = f"Brand: {brand_name}\nDescription: {product_description}"

    # Step A: Determine competitor targets (Manual override vs. Groq Auto-Discovery)
    if manual_overrides:
        discovered_competitors = [
            {
                "company_name": target,
                "search_keyword": target,
                "reason": "Manual competitor override provided by user.",
            }
            for target in manual_overrides
        ]
    else:
        discovered_competitors = discover_competitors_with_groq(
            brand_name=brand_name,
            product_description=product_description,
            max_competitors=max_competitors,
        )
        # Fallback if LLM returns nothing
        if not discovered_competitors:
            discovered_competitors = [
                {
                    "company_name": "Burger King",
                    "search_keyword": "Burger King",
                    "reason": "Default fallback competitor.",
                }
            ]

    # Step B: Fetch & score ads for each discovered competitor via SocialCrawl
    ad_engine = SocialCrawlAdEngine(api_key=socialcrawl_api_key)
    all_scored = []

    for comp in discovered_competitors:
        keyword = comp.get("search_keyword") or comp.get("company_name")
        raw_ads = ad_engine.fetch_page_ads(search_term=keyword)
        if raw_ads:
            df = ad_engine.score_ads(raw_ads)
            if not df.empty:
                all_scored.append(df)

    if not all_scored:
        return pd.DataFrame(), discovered_competitors

    master_df = pd.concat(all_scored, ignore_index=True)
    master_df = master_df.sort_values(
        by="days_active", ascending=False
    ).reset_index(drop=True)

    # Step C: Generate creative briefs for top 3 longest-running ads across competitors
    top_ads = master_df.to_dict(orient="records")
    briefs = []
    for ad in top_ads[:3]:
        brief = generate_brand_brief(ad, brand_profile)
        briefs.append({**ad, **brief})

    results_df = pd.DataFrame(briefs)
    results_df.to_csv("master_creative_execution_briefs.csv", index=False)
    return results_df, discovered_competitors
