from __future__ import annotations

import time
from io import StringIO
from typing import Any

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

REQUEST_TIMEOUT = 30
CACHE_TTL_SECONDS = 60 * 60 * 6
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

app = FastAPI(title="Dota Counter Backend", version="1.0.0")
_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


class DotabuffHeroRequest(BaseModel):
    hero_slug: str
    localized_name: str


class DotabuffBatchRequest(BaseModel):
    heroes: list[DotabuffHeroRequest]


def fetch_dotabuff_worst_versus(hero_slug: str) -> list[dict[str, Any]]:
    cached_entry = _cache.get(hero_slug)
    now = time.time()
    if cached_entry and now - cached_entry[0] < CACHE_TTL_SECONDS:
        return cached_entry[1]

    response = requests.get(
        f"https://www.dotabuff.com/heroes/{hero_slug}",
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    if response.status_code in {401, 403, 429}:
        raise HTTPException(status_code=502, detail=f"Dotabuff blocked request for slug '{hero_slug}'.")
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    target_table = None
    for table in tables:
        normalized_columns = [str(column).strip() for column in table.columns]
        if normalized_columns == ["Hero", "Disadvantage", "Win Rate", "Matches"]:
            target_table = table

    if target_table is None:
        parsed_rows: list[dict[str, Any]] = []
    else:
        normalized_df = target_table.copy()
        normalized_df.columns = ["Hero", "Disadvantage", "Win Rate", "Matches"]
        normalized_df["Hero"] = normalized_df["Hero"].astype(str).str.strip()
        normalized_df["Disadvantage"] = (
            normalized_df["Disadvantage"].astype(str).str.replace("%", "", regex=False)
        )
        normalized_df["Win Rate"] = normalized_df["Win Rate"].astype(str).str.replace("%", "", regex=False)
        normalized_df["Matches"] = normalized_df["Matches"].astype(str).str.replace(",", "", regex=False)
        parsed_rows = normalized_df.to_dict("records")

    _cache[hero_slug] = (now, parsed_rows)
    return parsed_rows


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dotabuff/test/{hero_slug}")
def dotabuff_test(hero_slug: str) -> dict[str, Any]:
    """Debug endpoint to inspect a single Dotabuff parse result."""
    try:
        rows = fetch_dotabuff_worst_versus(hero_slug)
    except HTTPException as exc:
        raise exc
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "hero_slug": hero_slug,
        "row_count": len(rows),
        "sample": rows[:5],
    }


@app.post("/dotabuff/worst-versus/batch")
def dotabuff_worst_versus_batch(payload: DotabuffBatchRequest) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for hero in payload.heroes:
        try:
            hero_rows = fetch_dotabuff_worst_versus(hero.hero_slug)
        except HTTPException as exc:
            errors.append({"hero_slug": hero.hero_slug, "detail": str(exc.detail)})
            continue
        except (requests.RequestException, ValueError) as exc:
            errors.append({"hero_slug": hero.hero_slug, "detail": str(exc)})
            continue

        for row in hero_rows:
            rows.append(
                {
                    "enemy_hero": hero.localized_name,
                    "localized_name": row["Hero"],
                    "dotabuff_disadvantage": pd.to_numeric(row["Disadvantage"], errors="coerce"),
                    "dotabuff_matches": pd.to_numeric(row["Matches"], errors="coerce"),
                    "dotabuff_enemy_hits": 1,
                }
            )

    return {"rows": rows, "errors": errors}
