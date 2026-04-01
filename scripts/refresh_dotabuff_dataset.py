from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import cloudscraper
import requests

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "dotabuff_worst_versus.json"
OPENDOTA_HEROES_URL = "https://api.opendota.com/api/heroes"
DOTABUFF_HERO_URL_TEMPLATE = "https://www.dotabuff.com/heroes/{hero_slug}"
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
PATCH_VERSION = "7.41a"
PATCH_SOURCE_URL = "https://www.dota2.com/patches/7.41a"
PATCH_RELEASE_DATE = "2026-03-28"


def localized_name_to_slug(localized_name: str) -> str:
    """Convert a localized hero name into the Dotabuff slug format."""
    normalized = localized_name.strip().lower()
    normalized = normalized.replace("'", "")
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def fetch_heroes() -> list[dict]:
    response = requests.get(
        OPENDOTA_HEROES_URL,
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("OpenDota /heroes response is not a list.")
    return payload


def parse_worst_versus_table(html: str) -> list[dict]:
    tables = pd.read_html(StringIO(html))
    target_table = None
    for table in tables:
        normalized_columns = [str(column).strip() for column in table.columns]
        if {"Disadvantage", "Win Rate", "Matches"}.issubset(set(normalized_columns)):
            target_table = table
            break

    if target_table is None:
        return []

    normalized_df = target_table.copy()
    normalized_columns = [str(column).strip() for column in normalized_df.columns]
    hero_column = "Hero.1" if "Hero.1" in normalized_columns else "Hero"
    normalized_df = normalized_df.loc[:, [hero_column, "Disadvantage", "Win Rate", "Matches"]].copy()
    normalized_df.columns = ["hero", "disadvantage_pct", "win_rate_pct", "matches"]
    normalized_df["hero"] = normalized_df["hero"].astype(str).str.strip()
    normalized_df["disadvantage_pct"] = pd.to_numeric(
        normalized_df["disadvantage_pct"].astype(str).str.replace("%", "", regex=False),
        errors="coerce",
    )
    normalized_df["win_rate_pct"] = pd.to_numeric(
        normalized_df["win_rate_pct"].astype(str).str.replace("%", "", regex=False),
        errors="coerce",
    )
    normalized_df["matches"] = pd.to_numeric(
        normalized_df["matches"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0).astype(int)
    normalized_df = normalized_df.dropna(subset=["hero", "disadvantage_pct", "win_rate_pct"])
    return normalized_df.to_dict("records")


def fetch_dotabuff_worst_versus(localized_name: str) -> list[dict]:
    hero_slug = localized_name_to_slug(localized_name)
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "mobile": False})
    response = scraper.get(
        DOTABUFF_HERO_URL_TEMPLATE.format(hero_slug=hero_slug),
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    return parse_worst_versus_table(response.text)


def build_payload() -> dict:
    heroes = fetch_heroes()
    hero_names = sorted(
        str(hero.get("localized_name", "")).strip()
        for hero in heroes
        if str(hero.get("localized_name", "")).strip()
    )

    dataset = {
        "updated_at": datetime.now(timezone.utc).date().isoformat(),
        "source": "Dotabuff Worst Versus",
        "patch_version": PATCH_VERSION,
        "patch_release_date": PATCH_RELEASE_DATE,
        "patch_source_url": PATCH_SOURCE_URL,
        "failed_heroes": [],
        "heroes": {},
    }

    for index, hero_name in enumerate(hero_names, start=1):
        print(f"[{index}/{len(hero_names)}] Fetching {hero_name}")
        try:
            dataset["heroes"][hero_name] = fetch_dotabuff_worst_versus(hero_name)
        except requests.RequestException as exc:
            print(f"  ! Failed for {hero_name}: {exc}")
            dataset["heroes"][hero_name] = []
            dataset["failed_heroes"].append(hero_name)

    return dataset


def main() -> int:
    payload = build_payload()
    DATASET_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote refreshed Dotabuff dataset to {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
