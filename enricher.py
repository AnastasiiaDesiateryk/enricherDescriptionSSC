import json
import re
import time

import httpx
import pandas as pd
from bs4 import BeautifulSoup
import trafilatura

from llm_openai import rewrite_description
from error_logging import (
    ensure_error_columns,
    normalize_url,
    domain_of,
    safe_str,
    mark_skipped,
    mark_success,
    mark_empty,
    mark_error,
)

# ---------------------------------------------------------------------
# Logging strategy (planned improvement)
#
# TODO (Next step):
#   Replace ad-hoc print statements with Python's built-in `logging` module.
#
# Proposed logging design:
#   - Configure logging once at application startup (entry-point).
#   - Use structured, level-based logs:
#       * INFO    : high-level pipeline progress (start/end of processing)
#       * WARNING : non-fatal issues (e.g., partial content extraction)
#       * ERROR   : external service failures (LLM errors, request failures)
#   - Use a consistent log format to support aggregation and monitoring in production.
#
# Rationale:
#   This enables observability in production environments and avoids relying
#   on stdout prints for troubleshooting.
# ---------------------------------------------------------------------

TIMEOUT_S = 20
PER_DOMAIN_DELAY_S = 0.8
MAX_TEXT = 6000

# How much text to send to the LLM (keeps cost/time bounded)
LLM_CONTEXT_CHARS = 2500

UA = "Mozilla/5.0 (compatible; SSCTechCompanyEnricher/1.0; +https://example.com)"


def get_meta_desc(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        t = og["content"].strip()
        if t:
            return t

    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        t = md["content"].strip()
        if t:
            return t

    return None


def get_jsonld_desc(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for s in scripts:
        raw = (s.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if isinstance(obj, dict) and isinstance(obj.get("description"), str):
                t = obj["description"].strip()
                if t:
                    return t
    return None


def extract_main_text(html: str, url: str) -> str | None:
    try:
        txt = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not txt:
            return None
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt if len(txt) > 200 else None
    except Exception:
        return None


def simple_summary(text: str, max_sentences: int = 2) -> str:
    """Дешёвый fallback, если main_text большой/сырой."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p.strip() for p in parts if len(p.strip()) > 30]
    if parts:
        return " ".join(parts[:max_sentences])[:600]
    return text[:300]


def enrich_dataframe(df: pd.DataFrame, sheet_name: str = "Database") -> pd.DataFrame:
    if "Company" not in df.columns or "Website" not in df.columns:
        raise ValueError("No Company/Website in Database.")

    df = ensure_error_columns(df)

    last_hit: dict[str, float] = {}
    headers = {"User-Agent": UA}

    with httpx.Client(timeout=TIMEOUT_S, headers=headers, follow_redirects=True) as client:
        for i, row in df.iterrows():
            company = safe_str(row.get("Company", ""))
            url = normalize_url(row.get("Website", ""))

            if not company and not url:
                mark_skipped(df, i, "Empty row (Company and Website missing)")
                continue
            if not url:
                mark_skipped(df, i, "Website is empty")
                continue

            domain = domain_of(url)

            prev = last_hit.get(domain)
            if prev is not None:
                sleep_for = PER_DOMAIN_DELAY_S - (time.time() - prev)
                if sleep_for > 0:
                    time.sleep(sleep_for)

            try:
                r = client.get(url)
                r.raise_for_status()
                html = r.text

                # 1) Build a single "raw" description first (scraper-only baseline)
                raw_desc = get_meta_desc(html) or get_jsonld_desc(html)
                raw_source = "meta/jsonld"

                if not raw_desc:
                    main_txt = extract_main_text(html, url)
                    if not main_txt:
                        mark_empty(df, i, "No description found (meta/jsonld/main_text)")
                        last_hit[domain] = time.time()
                        continue

                    raw_desc = simple_summary(main_txt[:MAX_TEXT])
                    raw_source = "main_text"

                # 2) Exactly ONE LLM call to improve the raw description
                improved = None
                try:
                    improved = rewrite_description(
                        company=company,
                        website=url,
                        extracted_text=raw_desc[:LLM_CONTEXT_CHARS],
                         # Intentionally not passing a "current description" field,
                        # as the underlying website content may change over time.
                        current_description="",  
                    )
                    improved = (improved or "").strip()
                except Exception as e:
                    # Log any LLM issues but keep the pipeline running (fallback to scraper output)
                    print(
                        "[LLM ERROR]",
                        f"company={company}",
                        f"url={url}",
                        f"type={type(e).__name__}",
                        f"message={e}",
                    )
                    improved = None

                # 3) If LLM did not return a usable result, keep the scraper-only description
                if improved and len(improved) >= 30:
                    mark_success(df, i, improved, raw_source)
                else:
                    mark_success(df, i, raw_desc, f"{raw_source}+llm_fallback")

            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "NA"
                mark_error(df, i, f"error:http:{status}", f"HTTP {status} for {url}")
            except httpx.TimeoutException:
                mark_error(df, i, "error:timeout", f"Timeout for {url}")
            except httpx.RequestError as e:
                mark_error(df, i, "error:request", f"Request error: {type(e).__name__} ({e}) for {url}")
            except Exception as e:
                mark_error(df, i, f"error:{type(e).__name__}", f"{type(e).__name__}: {e}")

            last_hit[domain] = time.time()

    return df


# ---------------------------------------------------------------------
# Deployment notes (environment configuration)
#
# Configure the following environment variables in your deployment platform:
#   - OPENAI_API_KEY : API key used by llm_openai.py to call the LLM
#   - OPENAI_MODEL   : optional override for the model name (e.g., gpt-5-mini)
#
# The application is designed to be resilient:
#   - The scraper runs first and produces a baseline description.
#   - The LLM is an optional enhancement step.
#   - If the LLM fails (auth, rate limit, timeout, etc.), the pipeline falls back
#     to the scraper output and continues without crashing.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# LLM instructions (high-level policy)
#
# Purpose:
#   Improve/normalize "solution descriptions" in a business database.
#
# Inputs:
#   - Company name
#   - Website
#   - Extracted text (scraper baseline; may be short or noisy)
#
# Requirements:
#   1) Produce a concise, neutral solution description (1–2 sentences).
#   2) Use only information that can reasonably be inferred from the provided text/website.
#   3) Avoid invented facts, products, markets, or unsupported claims.
#   4) Avoid marketing fluff and buzzwords; keep a database-style tone.
#   5) Output must be English.
#
# If information is insufficient:
#   Provide a cautious, minimal description instead of guessing.
#
# Note:
#   We intentionally do not pass a previously stored description as authoritative input,
#   since the company's public website content may evolve over time.
# ---------------------------------------------------------------------