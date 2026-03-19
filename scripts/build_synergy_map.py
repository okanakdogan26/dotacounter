from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SYNERGY_CONFIG_PATH = ROOT / "data" / "synergy_map.json"

API_BASE_URL = "https://api.opendota.com/api"
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
LOOKBACK_DAYS = 180
MIN_PAIR_GAMES = 25
TOP_SYNERGIES_PER_ALLY = 12
REQUEST_PAUSE_SECONDS = 0.75
MAX_RETRIES = 6


def fetch_json(path: str, params: dict[str, str] | None = None) -> object:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        response = None
        try:
            response = requests.get(
                f"{API_BASE_URL}{path}",
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers=REQUEST_HEADERS,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else min(10.0 * attempt, 60.0)
                print(f"Rate limited on {path}; retrying in {wait_seconds:.1f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                raise
            wait_seconds = min(5.0 * attempt, 30.0)
            print(f"Request failed for {path}; retrying in {wait_seconds:.1f}s ({exc})")
            time.sleep(wait_seconds)

    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to fetch {path}")


def fetch_heroes() -> list[dict]:
    payload = fetch_json("/heroes")
    if not isinstance(payload, list):
        raise ValueError("OpenDota /heroes did not return a list.")
    return payload


def fetch_explorer_rows(sql: str) -> list[dict]:
    payload = fetch_json("/explorer", params={"sql": sql})
    if not isinstance(payload, dict):
        raise ValueError("OpenDota /explorer did not return an object.")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("OpenDota /explorer rows is not a list.")
    return rows


def build_baseline_sql(cutoff_ts: int) -> str:
    return f"""
    SELECT
        pb.hero_id,
        COUNT(*) AS games_total,
        SUM(
            CASE
                WHEN (pb.team = 0 AND m.radiant_win)
                  OR (pb.team = 1 AND NOT m.radiant_win)
                THEN 1
                ELSE 0
            END
        ) AS wins_total
    FROM matches m
    JOIN picks_bans pb
      ON m.match_id = pb.match_id
    WHERE m.start_time >= {cutoff_ts}
      AND pb.is_pick = TRUE
    GROUP BY pb.hero_id
    HAVING COUNT(*) >= {MIN_PAIR_GAMES}
    """.strip()


def build_pair_sql(ally_hero_id: int, cutoff_ts: int) -> str:
    return f"""
    WITH ally_matches AS (
        SELECT
            m.match_id,
            pb.team AS ally_team
        FROM matches m
        JOIN picks_bans pb
          ON m.match_id = pb.match_id
        WHERE m.start_time >= {cutoff_ts}
          AND pb.is_pick = TRUE
          AND pb.hero_id = {ally_hero_id}
    )
    SELECT
        pb.hero_id,
        COUNT(*) AS games_together,
        SUM(
            CASE
                WHEN (pb.team = 0 AND m.radiant_win)
                  OR (pb.team = 1 AND NOT m.radiant_win)
                THEN 1
                ELSE 0
            END
        ) AS wins_together
    FROM ally_matches am
    JOIN matches m
      ON m.match_id = am.match_id
    JOIN picks_bans pb
      ON pb.match_id = am.match_id
    WHERE pb.is_pick = TRUE
      AND pb.team = am.ally_team
      AND pb.hero_id != {ally_hero_id}
    GROUP BY pb.hero_id
    HAVING COUNT(*) >= {MIN_PAIR_GAMES}
    ORDER BY games_together DESC
    """.strip()


def load_existing_config() -> dict:
    if not SYNERGY_CONFIG_PATH.exists():
        return {"ally_synergy_map": {}, "role_synergy_weights": {}}

    with SYNERGY_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        payload = json.load(config_file)
    if not isinstance(payload, dict):
        raise ValueError("Existing synergy config is not a JSON object.")
    payload.setdefault("ally_synergy_map", {})
    payload.setdefault("role_synergy_weights", {})
    return payload


def save_config(payload: dict) -> None:
    SYNERGY_CONFIG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_synergy_payload() -> dict:
    existing_config = load_existing_config()
    existing_source = existing_config.get("source", {})
    generated_allies = set(existing_source.get("generated_allies", []))
    existing_ally_map = existing_config.get("ally_synergy_map", {})

    heroes = fetch_heroes()
    hero_name_by_id = {int(hero["id"]): hero["localized_name"] for hero in heroes if "id" in hero}

    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp())
    baseline_rows = fetch_explorer_rows(build_baseline_sql(cutoff_ts))
    baseline_by_id: dict[int, tuple[int, int]] = {}
    for row in baseline_rows:
        hero_id = int(row["hero_id"])
        baseline_by_id[hero_id] = (int(row["games_total"]), int(row["wins_total"]))

    ally_synergy_map: dict[str, dict[str, float]] = {
        hero_name: existing_ally_map.get(hero_name, {})
        for hero_name in hero_name_by_id.values()
        if hero_name in generated_allies
    }

    hero_ids = sorted(hero_name_by_id)
    for index, ally_hero_id in enumerate(hero_ids, start=1):
        ally_name = hero_name_by_id[ally_hero_id]
        if ally_name in generated_allies:
            print(f"[{index}/{len(hero_ids)}] Skipping {ally_name} (already generated)")
            continue
        print(f"[{index}/{len(hero_ids)}] Building synergy for {ally_name}")

        pair_rows = fetch_explorer_rows(build_pair_sql(ally_hero_id, cutoff_ts))
        scored_rows: list[tuple[str, float]] = []

        for row in pair_rows:
            candidate_id = int(row["hero_id"])
            candidate_name = hero_name_by_id.get(candidate_id)
            if not candidate_name:
                continue

            baseline = baseline_by_id.get(candidate_id)
            if not baseline:
                continue

            games_total, wins_total = baseline
            games_together = int(row["games_together"])
            wins_together = int(row["wins_together"])
            if games_together < MIN_PAIR_GAMES or games_total <= 0:
                continue

            baseline_win_rate = wins_total / games_total
            pair_win_rate = wins_together / games_together
            lift = pair_win_rate - baseline_win_rate
            sample_factor = games_together / (games_together + 100.0)
            synergy_score = round(max(lift, 0.0) * 100.0 * sample_factor, 2)

            if synergy_score > 0:
                scored_rows.append((candidate_name, synergy_score))

        scored_rows.sort(key=lambda item: item[1], reverse=True)
        ally_synergy_map[ally_name] = dict(scored_rows[:TOP_SYNERGIES_PER_ALLY])
        generated_allies.add(ally_name)
        existing_config["updated_at"] = datetime.now(timezone.utc).date().isoformat()
        existing_config["source"] = {
            "provider": "OpenDota Explorer",
            "lookback_days": LOOKBACK_DAYS,
            "min_pair_games": MIN_PAIR_GAMES,
            "top_synergies_per_ally": TOP_SYNERGIES_PER_ALLY,
            "generated_allies": sorted(generated_allies),
        }
        existing_config["ally_synergy_map"] = ally_synergy_map
        save_config(existing_config)
        time.sleep(REQUEST_PAUSE_SECONDS)

    existing_config["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    existing_config["source"] = {
        "provider": "OpenDota Explorer",
        "lookback_days": LOOKBACK_DAYS,
        "min_pair_games": MIN_PAIR_GAMES,
        "top_synergies_per_ally": TOP_SYNERGIES_PER_ALLY,
        "generated_allies": sorted(generated_allies),
    }
    existing_config["ally_synergy_map"] = ally_synergy_map
    return existing_config


def main() -> int:
    payload = build_synergy_payload()
    save_config(payload)
    print(f"Wrote synergy map to {SYNERGY_CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
