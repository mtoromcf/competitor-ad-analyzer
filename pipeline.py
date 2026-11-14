from datetime import datetime, timezone
import json
import os
import re
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
    fb_handle: str
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
) -> tuple[list[dict], str]:
    """Uses Groq to identify top direct competitors and their exact Facebook Page handles."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return [], "Groq discovery skipped: GROQ_API_KEY is empty."

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
        f"with exact keys:\n"
        f"- 'company_name': official brand name (e.g., 'Burger King')\n"
        f"- 'search_keyword': official Facebook Page display name (e.g., 'Burger King')\n"
        f"- 'fb_handle': lowercase official Facebook Page slug without spaces or punctuation (e.g., 'burgerking', 'wendys', 'tacobell')\n"
        f"- 'reason': 1-sentence explanation of why they compete."
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
        raw_content = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)

        if isinstance(parsed, list):
            competitors = parsed
        elif isinstance(parsed, dict):
            competitors = (
                parsed.get("suggested_competitors")
                or parsed.get("competitors")
                or next((v for v in parsed.values() if isinstance(v, list)), [])
            )
        else:
            competitors = []

        cleaned = []
        for item in competitors:
            if isinstance(item, dict) and (item.get("company_name") or item.get("search_keyword")):
                name = str(item.get("company_name") or item.get("search_keyword")).strip()
                cleaned.append(
                    {
                        "company_name": name,
                        "search_keyword": str(item.get("search_keyword") or name).strip(),
                        "fb_handle": str(
                            item.get("fb_handle")
                            or re.sub(r"[^a-zA-Z0-9.]", "", name).lower()
                        ).strip(),
                        "reason": str(item.get("reason") or "Direct market competitor."),
                    }
                )

        return cleaned[:max_competitors], ""
    except Exception as e:
        return [], f"Groq discovery error: {e}"


# ==========================================
# 3. SOCIALCRAWL AD ENGINE
# ==========================================
class SocialCrawlAdEngine:

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()
        self.company_ads_url = (
            "https://www.socialcrawl.dev/v1/facebook/adlibrary/company/ads"
        )
        self.company_search_url = (
            "https://www.socialcrawl.dev/v1/facebook/adlibrary/search/companies"
        )
        self.credits_remaining = None
        self.status_logs = []

    def _extract_items(self, payload) -> list:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        data_block = payload.get("data")
        if isinstance(data_block, dict):
            for key in ("items", "ads", "results", "records"):
                if isinstance(data_block.get(key), list):
                    return data_block[key]
        if isinstance(data_block, list):
            return data_block
        for key in ("items", "ads", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []

    def _resolve_page_id(self, search_term: str) -> str | None:
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        try:
            res = requests.get(
                self.company_search_url,
                headers=headers,
                params={"query": search_term},
                timeout=20,
            )
            if res.status_code != 200:
                return None

            payload = res.json()
            if isinstance(payload, dict) and payload.get("credits_remaining") is not None:
                self.credits_remaining = payload.get("credits_remaining")

            companies = self._extract_items(payload)
            if not companies:
                return None

            target_lower = search_term.lower().strip()
            best_match = companies[0]
            best_score = -1

            for comp in companies:
                if not isinstance(comp, dict):
                    continue
                author = comp.get("author") if isinstance(comp.get("author"), dict) else {}
                name = str(
                    comp.get("name")
                    or comp.get("page_name")
                    or author.get("name")
                    or comp.get("title")
                    or ""
                )
                name_lower = name.lower().strip()
                likes = int(
                    comp.get("likes")
                    or comp.get("page_like_count")
                    or comp.get("followers")
                    or 0
                )
                verified_bonus = 10_000_000 if comp.get("verification") or comp.get("is_verified") else 0
                exact_bonus = 50_000_000 if name_lower == target_lower else (
                    5_000_000 if target_lower in name_lower else 0
                )
                score = exact_bonus + verified_bonus + likes
                if score > best_score:
                    best_score = score
                    best_match = comp

            if not isinstance(best_match, dict):
                return None
            author = best_match.get("author") if isinstance(best_match.get("author"), dict) else {}
            page_id = (
                best_match.get("pageId")
                or best_match.get("page_id")
                or author.get("id")
                or best_match.get("id")
            )
            return str(page_id) if page_id else None
        except Exception:
            return None

    def _query_company_ads(self, query_params: dict) -> list:
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        res = requests.get(
            self.company_ads_url, headers=headers, params=query_params, timeout=25
        )
        if res.status_code != 200:
            return []
        payload = res.json()
        if isinstance(payload, dict):
            if payload.get("credits_remaining") is not None:
                self.credits_remaining = payload.get("credits_remaining")
            if not payload.get("success", True):
                return []
        return self._extract_items(payload)

    def fetch_page_ads(
        self,
        search_term: str,
        fb_handle: str = "",
        country: str = "US",
        max_pages: int = 1,
    ) -> list:
        if not self.api_key:
            self.status_logs.append(f"{search_term}: Missing SocialCrawl API key -> using mock data.")
            return self._get_mock_ads(search_term)

        clean_handle = fb_handle or re.sub(r"[^a-zA-Z0-9.]", "", search_term).lower()

        try:
            items = self._query_company_ads(
                {"companyName": clean_handle, "country": country, "status": "ACTIVE"}
            )

            if not items:
                page_id = self._resolve_page_id(search_term)
                if page_id:
                    items = self._query_company_ads(
                        {"pageId": page_id, "country": country, "status": "ACTIVE"}
                    )

            if not items and clean_handle:
                items = self._query_company_ads(
                    {"companyName": clean_handle, "status": "ACTIVE"}
                )

            if not items:
                self.status_logs.append(
                    f"{search_term}: 0 active ads returned (handle='{clean_handle}') -> using mock data."
                )
                return self._get_mock_ads(search_term)

            for item in items:
                if isinstance(item, dict) and not item.get("page_name"):
                    item["page_name"] = search_term

            self.status_logs.append(
                f"{search_term}: Live hit ({len(items)} ads fetched)."
            )
            return items

        except Exception as e:
            self.status_logs.append(f"{search_term}: Connection exception ({e}) -> using mock data.")
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
            if not isinstance(ad, dict):
                continue

            snapshot = ad.get("snapshot") if isinstance(ad.get("snapshot"), dict) else {}
            author = ad.get("author") if isinstance(ad.get("author"), dict) else {}
            ext = ad.get("ext") if isinstance(ad.get("ext"), dict) else {}

            start_raw = (
                ad.get("start_date")
                or ad.get("ad_delivery_start_time")
                or ad.get("published_at")
                or ad.get("created_at")
                or ext.get("start_date")
            )
            start_dt = self._parse_start_date(start_raw)
            days_active = max((now - start_dt).days, 1)

            page_name = (
                author.get("name")
                or ad.get("page_name")
                or ad.get("advertiser_name")
                or snapshot.get("page_name")
                or "Unknown Competitor"
            )

            headline = (
                ad.get("headline")
                or ad.get("title")
                or snapshot.get("title")
                or snapshot.get("link_description")
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
                or ad.get("caption")
                or ad.get("content")
                or ad.get("description")
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

            cta = ext.get("cta_text") or snapshot.get("cta_text") or ad.get("cta_text") or ""
            if not headline and not primary_text:
                primary_text = f"[Visual/Video Ad Creative{f' - CTA: {cta}' if cta else ''}]"

            processed.append(
                {
                    "ad_id": str(
                        ad.get("id")
                        or ad.get("ad_archive_id")
                        or ad.get("ad_id")
                        or "unknown"
                    ),
                    "page_name": str(page_name),
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
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
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

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        if isinstance(parsed, dict) and parsed:
            return parsed
    except Exception as e:
        print(f"Groq Brief Generation Error: {e}")

    return {
        "extracted_hook": ad_record.get("headline") or ad_record.get("primary_text", "")[:80],
        "hook_type": "Value & Social Proof",
        "emotional_trigger": "FOMO / Convenience",
        "adapted_hook_1": f"Switch to {brand_profile.splitlines()[0].replace('Brand: ', '')} today and see the difference.",
        "adapted_hook_2": "Stop settling for less—get more value on every order.",
        "adapted_hook_3": "Limited-time offer built for smart buyers.",
        "primary_text_draft": ad_record.get("primary_text", ""),
        "visual_execution_idea": "Split-screen product comparison with bold headline overlay and clear call-to-action button.",
    }


# ==========================================
# 5. MASTER EXECUTION PIPELINE
# ==========================================
def run_end_to_end_competitor_pipeline(
    brand_name: str,
    product_description: str,
    socialcrawl_api_key: str = "",
    manual_overrides: list[str] = None,
    max_competitors: int = 3,
) -> tuple[pd.DataFrame, list[dict], dict]:
    brand_profile = f"Brand: {brand_name}\nDescription: {product_description}"
    extra_logs = []

    if manual_overrides:
        discovered_competitors = [
            {
                "company_name": target,
                "search_keyword": target,
                "fb_handle": re.sub(r"[^a-zA-Z0-9.]", "", target).lower(),
                "reason": "Manual competitor override provided by user.",
            }
            for target in manual_overrides
        ]
    else:
        discovered_competitors, groq_err = discover_competitors_with_groq(
            brand_name=brand_name,
            product_description=product_description,
            max_competitors=max_competitors,
        )
        if groq_err:
            extra_logs.append(groq_err)
        if not discovered_competitors:
            discovered_competitors = [
                {
                    "company_name": "Burger King",
                    "search_keyword": "Burger King",
                    "fb_handle": "burgerking",
                    "reason": "Default fallback competitor.",
                }
            ]

    ad_engine = SocialCrawlAdEngine(api_key=socialcrawl_api_key)
    all_scored = []

    for comp in discovered_competitors:
        keyword = comp.get("search_keyword") or comp.get("company_name")
        handle = comp.get("fb_handle", "")
        raw_ads = ad_engine.fetch_page_ads(search_term=keyword, fb_handle=handle)
        if raw_ads:
            df = ad_engine.score_ads(raw_ads)
            if not df.empty:
                all_scored.append(df)

    diagnostics = {
        "credits_remaining": ad_engine.credits_remaining,
        "status_logs": extra_logs + ad_engine.status_logs,
    }

    if not all_scored:
        return pd.DataFrame(), discovered_competitors, diagnostics

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
    return results_df, discovered_competitors, diagnostics
