"""
LinkedIn public job-search scraper, adapted from the user's original
linkedin_harvest.py so it can be called on demand, per-request, with
filters coming from the JOBBS web UI instead of a static config.json.

Notes on scope and risk (read this before deploying at scale):
- This reads LinkedIn's public, unauthenticated "jobs-guest" search pages.
  It does not log in and does not touch private data.
- Scraping LinkedIn is against LinkedIn's User Agreement. LinkedIn also
  actively rate-limits and blocks scraping traffic. Keep request volume
  modest, keep the built-in delays/backoff in place, and expect LinkedIn's
  HTML structure to change and break the CSS selectors below eventually.
- There is no official free LinkedIn Jobs API for this use case, which is
  why this project uses HTML scraping at all.
"""

import asyncio
import logging
import random
import re
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("jobbs.scraper")

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _headers() -> Dict[str, str]:
    h = BASE_HEADERS.copy()
    h["User-Agent"] = random.choice(USER_AGENTS)
    return h


class ScrapeCancelled(Exception):
    pass


async def _fetch_with_retry(client: httpx.AsyncClient, url: str, params=None, retries=3) -> Optional[str]:
    for attempt in range(1, retries + 1):
        try:
            await asyncio.sleep(random.uniform(0.6, 1.5))
            resp = await client.get(url, params=params, headers=_headers(), timeout=12.0)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (429, 999):
                logger.warning("Rate limited (%s), backing off, attempt %s/%s", resp.status_code, attempt, retries)
                await asyncio.sleep((2 ** attempt) + random.uniform(1, 2))
            else:
                logger.warning("HTTP %s for %s", resp.status_code, url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Network error on attempt %s: %s", attempt, exc)
            await asyncio.sleep(2 ** attempt)
    return None


def _parse_job_card(card: BeautifulSoup) -> Optional[Dict[str, str]]:
    try:
        title_el = card.select_one(".base-search-card__title, .job-search-card__title, h3")
        company_el = card.select_one(".base-search-card__subtitle, .job-search-card__company-name, h4")
        location_el = card.select_one(".job-search-card__location, .base-search-card__metadata")
        link_el = card.select_one("a.base-card__full-link, a.job-search-card__link, a")
        time_el = card.select_one("time")

        if not link_el or not title_el:
            return None

        raw_url = link_el.get("href", "").split("?")[0]
        job_id_match = re.search(r"(\d+)", raw_url)

        return {
            "id": job_id_match.group(1) if job_id_match else str(abs(hash(raw_url))),
            "title": title_el.get_text(strip=True),
            "company": company_el.get_text(strip=True) if company_el else "N/A",
            "location": location_el.get_text(strip=True) if location_el else "",
            "post_date": time_el.get("datetime") if time_el and time_el.get("datetime") else (
                time_el.get_text(strip=True) if time_el else "Recently"
            ),
            "full_url": raw_url,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("Card parse error: %s", exc)
        return None


async def _fetch_description(client: httpx.AsyncClient, job_id: str, sem: asyncio.Semaphore) -> str:
    async with sem:
        html = await _fetch_with_retry(client, f"{DETAIL_URL}/{job_id}")
    if not html:
        return "Description unavailable (LinkedIn did not return the page)."
    soup = BeautifulSoup(html, "html.parser")
    desc_el = soup.select_one(".show-more-less-html__markup, .description__text, .markup")
    if desc_el:
        clean = re.sub(r"\s+", " ", desc_el.get_text(separator=" ")).strip()
        return clean[:1200]
    return "Description not parseable."


async def _scrape_async(
    keyword: str,
    country: str,
    date_posted_param: str,
    workplace_type_param: str,
    max_results: int,
    concurrency: int,
    progress_cb=None,
    cancel_check=None,
) -> List[Dict]:
    listings: List[Dict] = []
    seen_ids = set()
    start = 0
    sem = asyncio.Semaphore(max(1, concurrency))

    location_param = "" if country.lower() == "worldwide" else country

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        while len(listings) < max_results:
            if cancel_check and cancel_check():
                raise ScrapeCancelled()

            params = {
                "keywords": keyword,
                "location": location_param,
                "f_TPR": date_posted_param,
                "start": start,
            }
            if workplace_type_param:
                params["f_WT"] = workplace_type_param

            html = await _fetch_with_retry(client, SEARCH_URL, params=params)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("li, div.base-search-card")
            if not cards:
                break

            new_cards = []
            for card in cards:
                parsed = _parse_job_card(card)
                if parsed and parsed["id"] not in seen_ids:
                    seen_ids.add(parsed["id"])
                    new_cards.append(parsed)

            if not new_cards:
                break

            remaining = max_results - len(listings)
            new_cards = new_cards[:remaining]

            desc_tasks = [_fetch_description(client, c["id"], sem) for c in new_cards]
            descriptions = await asyncio.gather(*desc_tasks)

            for item, desc in zip(new_cards, descriptions):
                item["description_snippet"] = desc
                item["platform"] = "LinkedIn"
                listings.append(item)
                if progress_cb:
                    progress_cb(len(listings), max_results)

            start += len(cards)

            if len(cards) < 10:
                # LinkedIn returned a short page; likely the last page of results
                break

    return listings


def run_search(
    keyword: str,
    country: str,
    date_posted_key: str,
    workplace_key: str,
    max_results: int,
    concurrency: int = 5,
    progress_cb=None,
    cancel_check=None,
) -> List[Dict]:
    """Synchronous entry point safe to call from a background thread."""
    from app.scraper.countries import DATE_POSTED, WORKPLACE_TYPES

    date_param = DATE_POSTED.get(date_posted_key, DATE_POSTED["any"])["f_tpr"]
    wt_param = WORKPLACE_TYPES.get(workplace_key, WORKPLACE_TYPES["any"])["f_wt"]
    max_results = max(1, min(int(max_results), 50))

    return asyncio.run(
        _scrape_async(
            keyword=keyword,
            country=country,
            date_posted_param=date_param,
            workplace_type_param=wt_param,
            max_results=max_results,
            concurrency=concurrency,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )
    )
