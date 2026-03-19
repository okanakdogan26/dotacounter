from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = "https://api.opendota.com/api"
STEAM_CDN_BASE_URL = "https://cdn.cloudflare.steamstatic.com"
STEAM_HERO_IMAGE_BASE_URL = f"{STEAM_CDN_BASE_URL}/apps/dota2/images/dota_react/heroes"
ROLE_OPTIONS = ["Hepsi", "Carry", "Support", "Mid", "Offlane", "Disabler", "Durable"]
REQUEST_TIMEOUT = 30
DEFAULT_MIN_GAMES_THRESHOLD = 50
DATA_DIR = Path(__file__).parent / "data"
DOTABUFF_DATASET_PATH = DATA_DIR / "dotabuff_worst_versus.json"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def matches_role_filter(roles: list[str], selected_role: str) -> bool:
    """Match UI roles against OpenDota roles and a few inferred lane heuristics."""
    role_set = set(roles)

    if selected_role == "Hepsi":
        return True
    if selected_role in {"Carry", "Support", "Disabler", "Durable"}:
        return selected_role in role_set
    if selected_role == "Mid":
        # OpenDota does not expose "Mid" directly in hero roles, so infer it from
        # common mid hero traits while excluding hard supports.
        return (
            "Support" not in role_set
            and bool(role_set.intersection({"Carry", "Nuker", "Escape", "Disabler"}))
        )
    if selected_role == "Offlane":
        # OpenDota does not expose "Offlane" directly either; durable initiators
        # and utility frontliners are the closest approximation.
        return (
            "Support" not in role_set
            and bool(role_set.intersection({"Durable", "Initiator", "Disabler"}))
        )
    return False


def get_hero_image_url(image_path: str | None, hero_name: str | None = None) -> str:
    """Convert OpenDota hero metadata into a full Steam CDN image URL."""
    if not image_path:
        if hero_name:
            hero_slug = hero_name.removeprefix("npc_dota_hero_")
            return f"{STEAM_HERO_IMAGE_BASE_URL}/{hero_slug}.png"
        return ""
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    if image_path.startswith("/apps/dota2/images/dota_react/heroes/"):
        return f"{STEAM_CDN_BASE_URL}{image_path}"
    return f"{STEAM_HERO_IMAGE_BASE_URL}/{image_path.rsplit('/', 1)[-1].replace('.full.png', '.png')}"


def render_selected_hero_grid(selected_hero_names: list[str], hero_df: pd.DataFrame) -> None:
    """Render selected enemy heroes as a compact image grid."""
    selected_df = hero_df[hero_df["localized_name"].isin(selected_hero_names)].copy()
    if selected_df.empty:
        return

    selected_df["image_url"] = selected_df.apply(
        lambda row: get_hero_image_url(row["img"], row.get("name")), axis=1
    )
    columns = st.columns(min(5, len(selected_df)))
    for index, (_, hero_row) in enumerate(selected_df.iterrows()):
        with columns[index % len(columns)]:
            if hero_row["image_url"]:
                st.image(hero_row["image_url"], width=140)
            st.markdown(f"**{hero_row['localized_name']}**")


def render_counter_cards(results_df: pd.DataFrame) -> None:
    """Render top counter heroes as visual cards."""
    top_results = results_df.head(6)
    if top_results.empty:
        return

    st.subheader("One Cikan Counterlar")
    columns = st.columns(4)
    for index, (_, hero_row) in enumerate(top_results.iterrows()):
        with columns[index % 4]:
            if hero_row.get("image_url"):
                st.image(hero_row["image_url"], width=180)
            st.markdown(f"**{hero_row['localized_name']}**")
            has_opendota_data = int(hero_row["games_played"]) > 0
            win_rate_text = (
                f"%{hero_row['win_rate']:.2f}"
                if has_opendota_data
                else "N/A (Dotabuff-only)"
            )
            games_text = str(int(hero_row["games_played"])) if has_opendota_data else "OpenDota veri yok"
            st.caption(
                f"Hibrit Skor: {hero_row['hybrid_score']:.2f} | "
                f"Win Rate: {win_rate_text} | "
                f"Mac: {games_text}"
            )


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_heroes() -> list[dict]:
    """Fetch and cache the hero catalog from OpenDota."""
    response = requests.get(f"{API_BASE_URL}/heroes", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    heroes = response.json()
    if not isinstance(heroes, list):
        raise ValueError("OpenDota hero response is not a list.")
    return heroes


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_counter_rows(selected_enemy_ids: tuple[int, ...], min_games_threshold: int) -> list[dict]:
    """Run the Explorer SQL query for the selected enemy heroes."""
    if not selected_enemy_ids:
        return []

    sql = build_counter_sql(selected_enemy_ids, min_games_threshold)
    response = requests.get(
        f"{API_BASE_URL}/explorer",
        params={"sql": sql},
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("OpenDota explorer response does not contain a valid rows list.")
    return rows


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_hero_matchups(hero_id: int) -> list[dict]:
    """Fetch historical hero matchup data for a single enemy hero."""
    response = requests.get(
        f"{API_BASE_URL}/heroes/{hero_id}/matchups",
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("OpenDota hero matchup response is not a list.")
    return rows


def build_counter_sql(selected_enemy_ids: Iterable[int], min_games_threshold: int) -> str:
    """Build the Explorer SQL query for counter heroes in the last 30 days."""
    enemy_ids = sorted({int(hero_id) for hero_id in selected_enemy_ids})
    if not enemy_ids:
        raise ValueError("At least one enemy hero is required.")

    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    enemy_id_csv = ", ".join(str(hero_id) for hero_id in enemy_ids)
    return f"""
    WITH enemy_matches AS (
        SELECT
            m.match_id,
            enemy_pb.team AS enemy_team,
            COUNT(DISTINCT enemy_pb.hero_id) AS matched_enemy_count
        FROM matches m
        JOIN picks_bans enemy_pb
            ON m.match_id = enemy_pb.match_id
        WHERE m.start_time >= {cutoff}
          AND enemy_pb.is_pick = TRUE
          AND enemy_pb.hero_id IN ({enemy_id_csv})
        GROUP BY m.match_id, enemy_pb.team
        HAVING COUNT(DISTINCT enemy_pb.hero_id) >= 1
    )
    SELECT
        pb.hero_id,
        COUNT(*) AS games_played,
        ROUND(AVG(em.matched_enemy_count), 2) AS avg_enemy_overlap,
        SUM(
            CASE
                WHEN (pb.team = 0 AND m.radiant_win)
                  OR (pb.team = 1 AND NOT m.radiant_win)
                THEN 1
                ELSE 0
            END
        ) AS wins,
        ROUND(
            100.0 * SUM(
                CASE
                    WHEN (pb.team = 0 AND m.radiant_win)
                      OR (pb.team = 1 AND NOT m.radiant_win)
                    THEN 1
                    ELSE 0
                END
            ) / COUNT(*),
            2
        ) AS win_rate
    FROM enemy_matches em
    JOIN matches m
        ON m.match_id = em.match_id
    JOIN picks_bans pb
        ON pb.match_id = em.match_id
    WHERE pb.is_pick = TRUE
      AND pb.team != em.enemy_team
    GROUP BY pb.hero_id
    HAVING COUNT(*) >= {int(min_games_threshold)}
    ORDER BY win_rate DESC, games_played DESC
    LIMIT 25
    """.strip()


def build_hero_dataframe(heroes: list[dict]) -> pd.DataFrame:
    """Normalize hero metadata into a DataFrame."""
    hero_df = pd.DataFrame(heroes)
    required_columns = {"id", "name", "localized_name", "roles"}
    missing_columns = required_columns.difference(hero_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Hero response is missing columns: {missing_text}")

    if "img" not in hero_df.columns:
        hero_df["img"] = ""

    hero_df = hero_df.loc[:, ["id", "name", "localized_name", "roles", "img"]].copy()
    hero_df["roles"] = hero_df["roles"].apply(lambda value: value if isinstance(value, list) else [])
    hero_df["img"] = hero_df["img"].fillna("")
    return hero_df


def build_fallback_matchup_dataframe(
    selected_enemy_ids: Iterable[int],
    min_games_threshold: int,
) -> pd.DataFrame:
    """
    Build fallback counter rows from hero matchup endpoints.

    Explorer data is professional-match focused and often sparse for normal pub drafts.
    This fallback aggregates per-enemy historical matchup data so the app remains usable.
    """
    aggregated_rows: list[dict] = []

    for enemy_id in selected_enemy_ids:
        for row in fetch_hero_matchups(int(enemy_id)):
            games_played = int(row.get("games_played", 0) or 0)
            enemy_wins = int(row.get("wins", 0) or 0)
            if games_played <= 0:
                continue

            aggregated_rows.append(
                {
                    "hero_id": int(row["hero_id"]),
                    "games_played": games_played,
                    "candidate_wins": max(games_played - enemy_wins, 0),
                    "enemy_overlap": 1,
                }
            )

    if not aggregated_rows:
        return pd.DataFrame()

    fallback_df = pd.DataFrame(aggregated_rows)
    fallback_df = (
        fallback_df.groupby("hero_id", as_index=False)
        .agg(
            games_played=("games_played", "sum"),
            wins=("candidate_wins", "sum"),
            enemy_overlap=("enemy_overlap", "sum"),
        )
    )
    fallback_df = fallback_df[fallback_df["games_played"] >= int(min_games_threshold)]
    if fallback_df.empty:
        return fallback_df

    fallback_df["avg_enemy_overlap"] = fallback_df["enemy_overlap"].astype(float)
    fallback_df["win_rate"] = (100.0 * fallback_df["wins"] / fallback_df["games_played"]).round(2)
    fallback_df = fallback_df.sort_values(["win_rate", "games_played"], ascending=[False, False])
    return fallback_df.loc[:, ["hero_id", "games_played", "wins", "win_rate", "avg_enemy_overlap"]]


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_dotabuff_dataset() -> dict:
    """Load locally curated Dotabuff worst-versus data."""
    if not DOTABUFF_DATASET_PATH.exists():
        return {"updated_at": None, "heroes": {}}

    with DOTABUFF_DATASET_PATH.open("r", encoding="utf-8") as dataset_file:
        payload = json.load(dataset_file)
    if not isinstance(payload, dict):
        raise ValueError("Dotabuff dataset must be a JSON object.")
    payload.setdefault("heroes", {})
    return payload


def build_dotabuff_signal_dataframe(selected_enemy_names: Iterable[str]) -> pd.DataFrame:
    """Aggregate locally stored Dotabuff worst-versus data across selected enemy heroes."""
    dataset = load_dotabuff_dataset()
    hero_map = dataset.get("heroes", {})
    signal_rows: list[dict] = []

    for enemy_name in selected_enemy_names:
        for entry in hero_map.get(enemy_name, []):
            signal_rows.append(
                {
                    "localized_name": entry["hero"],
                    "dotabuff_disadvantage": pd.to_numeric(entry["disadvantage_pct"], errors="coerce"),
                    "dotabuff_matches": pd.to_numeric(entry["matches"], errors="coerce"),
                    "dotabuff_enemy_hits": 1,
                }
            )

    if not signal_rows:
        return pd.DataFrame()

    signal_df = pd.DataFrame(signal_rows).dropna(subset=["localized_name"])
    if signal_df.empty:
        return signal_df

    signal_df = (
        signal_df.groupby("localized_name", as_index=False)
        .agg(
            dotabuff_disadvantage=("dotabuff_disadvantage", "mean"),
            dotabuff_matches=("dotabuff_matches", "sum"),
            dotabuff_enemy_hits=("dotabuff_enemy_hits", "sum"),
        )
        .sort_values(["dotabuff_enemy_hits", "dotabuff_disadvantage"], ascending=[False, False])
    )
    return signal_df


def prepare_results_dataframe(
    rows: list[dict],
    hero_df: pd.DataFrame,
    selected_role: str,
    selected_enemy_names: Iterable[str],
    dotabuff_signal_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convert explorer rows into a filtered, display-ready DataFrame."""
    results_df = pd.DataFrame(rows)
    if results_df.empty:
        results_df = pd.DataFrame(columns=["hero_id", "games_played", "wins", "win_rate", "avg_enemy_overlap"])

    if "avg_enemy_overlap" not in results_df.columns:
        results_df["avg_enemy_overlap"] = 0.0

    merged_df = results_df.merge(hero_df, left_on="hero_id", right_on="id", how="left")
    merged_df["localized_name"] = merged_df["localized_name"].fillna("Unknown Hero")
    merged_df["image_url"] = merged_df.apply(
        lambda row: get_hero_image_url(row["img"], row.get("name")), axis=1
    )
    enemy_name_set = set(selected_enemy_names)

    if enemy_name_set:
        merged_df = merged_df[~merged_df["localized_name"].isin(enemy_name_set)]

    if selected_role != "Hepsi":
        merged_df = merged_df[merged_df["roles"].apply(lambda roles: matches_role_filter(roles, selected_role))]

    if merged_df.empty:
        return merged_df

    merged_df["wins"] = pd.to_numeric(merged_df["wins"], errors="coerce").fillna(0).astype(int)
    merged_df["games_played"] = pd.to_numeric(merged_df["games_played"], errors="coerce").fillna(0).astype(int)
    merged_df["win_rate"] = pd.to_numeric(merged_df["win_rate"], errors="coerce").fillna(0.0)
    merged_df["avg_enemy_overlap"] = pd.to_numeric(
        merged_df["avg_enemy_overlap"], errors="coerce"
    ).fillna(0.0)

    if dotabuff_signal_df is not None and not dotabuff_signal_df.empty:
        merged_df = merged_df.merge(dotabuff_signal_df, on="localized_name", how="left")
    else:
        merged_df["dotabuff_disadvantage"] = 0.0
        merged_df["dotabuff_matches"] = 0
        merged_df["dotabuff_enemy_hits"] = 0

    # Include heroes that exist only in the local Dotabuff dataset but were absent
    # from the OpenDota result set, so strong manual counter signals can still appear.
    if dotabuff_signal_df is not None and not dotabuff_signal_df.empty:
        existing_names = set(merged_df["localized_name"].dropna().tolist())
        dotabuff_only_df = dotabuff_signal_df[~dotabuff_signal_df["localized_name"].isin(existing_names)].copy()
        if not dotabuff_only_df.empty:
            hero_lookup_df = hero_df.loc[:, ["localized_name", "name", "img", "roles"]].copy()
            dotabuff_only_df = dotabuff_only_df.merge(hero_lookup_df, on="localized_name", how="left")
            dotabuff_only_df["image_url"] = dotabuff_only_df.apply(
                lambda row: get_hero_image_url(row.get("img"), row.get("name")), axis=1
            )
            dotabuff_only_df["games_played"] = 0
            dotabuff_only_df["wins"] = 0
            dotabuff_only_df["win_rate"] = 0.0
            dotabuff_only_df["avg_enemy_overlap"] = 0.0
            merged_df = pd.concat([merged_df, dotabuff_only_df], ignore_index=True, sort=False)

    merged_df["dotabuff_disadvantage"] = pd.to_numeric(
        merged_df["dotabuff_disadvantage"], errors="coerce"
    ).fillna(0.0)
    merged_df["dotabuff_matches"] = pd.to_numeric(
        merged_df["dotabuff_matches"], errors="coerce"
    ).fillna(0).astype(int)
    merged_df["dotabuff_enemy_hits"] = pd.to_numeric(
        merged_df["dotabuff_enemy_hits"], errors="coerce"
    ).fillna(0).astype(int)

    selected_enemy_count = max(len(set(selected_enemy_names)), 1)
    merged_df["sample_factor"] = (merged_df["games_played"] / (merged_df["games_played"] + 75.0)).clip(0, 1)
    merged_df["overlap_factor"] = (merged_df["avg_enemy_overlap"] / selected_enemy_count).clip(0, 1)
    merged_df["role_factor"] = merged_df["roles"].apply(
        lambda roles: 1.0 if matches_role_filter(roles, selected_role) else 0.85
    )
    merged_df["stabilized_win_rate"] = (
        (merged_df["wins"] + 25.0) / (merged_df["games_played"] + 50.0) * 100.0
    ).round(2)
    merged_df["dotabuff_only"] = (
        (merged_df["games_played"] == 0) & (merged_df["dotabuff_enemy_hits"] > 0)
    )
    merged_df["confidence_score"] = (
        merged_df["stabilized_win_rate"] * 0.55
        + merged_df["sample_factor"] * 25.0
        + merged_df["overlap_factor"] * 15.0
        + merged_df["role_factor"] * 5.0
    ).round(2)
    merged_df.loc[merged_df["dotabuff_only"], "confidence_score"] = (
        25.0
        + (merged_df.loc[merged_df["dotabuff_only"], "dotabuff_disadvantage"] * 4.0)
        + (merged_df.loc[merged_df["dotabuff_only"], "dotabuff_enemy_hits"] * 5.0)
        + ((merged_df.loc[merged_df["dotabuff_only"], "dotabuff_matches"] / 10000.0).clip(0, 4.0))
    ).round(2)
    merged_df["hybrid_score"] = (
        merged_df["confidence_score"]
        + (merged_df["dotabuff_disadvantage"] * 1.5)
        + (merged_df["dotabuff_enemy_hits"] * 3.0)
        + ((merged_df["dotabuff_matches"] / 10000.0).clip(0, 3.0))
    ).round(2)
    merged_df = merged_df.sort_values(
        ["hybrid_score", "confidence_score", "games_played"], ascending=[False, False, False]
    )

    return merged_df.loc[
        :,
        [
            "image_url",
            "localized_name",
            "games_played",
            "wins",
            "win_rate",
            "stabilized_win_rate",
            "avg_enemy_overlap",
            "sample_factor",
            "overlap_factor",
            "confidence_score",
            "dotabuff_disadvantage",
            "dotabuff_matches",
            "dotabuff_enemy_hits",
            "hybrid_score",
            "roles",
        ],
    ]


def render_sidebar(hero_df: pd.DataFrame) -> tuple[list[str], str, int]:
    """Render sidebar controls and return current selections."""
    hero_names = hero_df["localized_name"].sort_values().tolist()

    st.sidebar.header("Filtreler")
    selected_heroes = st.sidebar.multiselect(
        "Rakip herolar",
        options=hero_names,
        max_selections=5,
        help="En fazla 5 rakip hero secin.",
    )
    selected_role = st.sidebar.selectbox("Rol filtresi", ROLE_OPTIONS)
    min_games_threshold = st.sidebar.slider(
        "Mac sayisi esigi",
        min_value=20,
        max_value=100,
        value=DEFAULT_MIN_GAMES_THRESHOLD,
        step=5,
        help="Sadece bu esik ve uzerindeki mac sayisina sahip counter onerileri gosterilir.",
    )
    return selected_heroes, selected_role, min_games_threshold


def main() -> None:
    st.set_page_config(page_title="Dota 2 Counter Picker", page_icon=":crossed_swords:", layout="wide")
    st.title("Dota 2 Counter Picker")

    try:
        heroes = fetch_heroes()
        hero_df = build_hero_dataframe(heroes)
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Hero listesi alinamadi: {exc}")
        return

    selected_hero_names, selected_role, min_games_threshold = render_sidebar(hero_df)
    hero_name_to_id = hero_df.set_index("localized_name")["id"].to_dict()
    selected_enemy_ids = tuple(hero_name_to_id[name] for name in selected_hero_names)

    st.caption(
        f"OpenDota verileri ile son 30 gunde secili rakiplere karsi en iyi kahramanlari bulun. "
        f"Su anki minimum orneklem esigi: {min_games_threshold} mac."
    )

    st.write("Rakip takimi secip uygun counter onerilerini inceleyin.")

    if not selected_enemy_ids:
        st.info("Devam etmek icin kenar cubugundan en az bir rakip hero secin.")
        return

    st.subheader("Secili Rakipler")
    render_selected_hero_grid(selected_hero_names, hero_df)

    try:
        rows = fetch_counter_rows(selected_enemy_ids, min_games_threshold)
    except requests.RequestException as exc:
        st.error(f"OpenDota Explorer API baglantisinda hata olustu: {exc}")
        return
    except ValueError as exc:
        st.error(f"Explorer verisi islenemedi: {exc}")
        return

    dotabuff_signal_df = build_dotabuff_signal_dataframe(selected_hero_names)
    dotabuff_dataset = load_dotabuff_dataset()
    dotabuff_status = (
        f"yerel dataset aktif (guncelleme: {dotabuff_dataset.get('updated_at', 'bilinmiyor')})"
        if not dotabuff_signal_df.empty
        else "yerel dataset bagli, secili hero icin kayit yok"
    )

    data_source_label = "OpenDota Explorer"
    if rows:
        results_df = prepare_results_dataframe(
            rows, hero_df, selected_role, selected_hero_names, dotabuff_signal_df
        )
    else:
        try:
            fallback_rows_df = build_fallback_matchup_dataframe(selected_enemy_ids, min_games_threshold)
        except (requests.RequestException, ValueError) as exc:
            st.error(f"OpenDota matchup verisi alinamadi: {exc}")
            return

        if fallback_rows_df.empty:
            st.warning(
                "Secili rakipler icin yeterli veri bulunamadi. Esigi dusurup tekrar deneyin."
            )
            return

        data_source_label = "OpenDota Hero Matchups"
        results_df = prepare_results_dataframe(
            fallback_rows_df.to_dict("records"),
            hero_df,
            selected_role,
            selected_hero_names,
            dotabuff_signal_df,
        )

    if results_df.empty:
        st.warning(
            "Secilen rol icin yeterli veri bulunamadi. Farkli bir rol, hero kombinasyonu "
            "veya daha dusuk mac esigi deneyin."
        )
        return

    st.caption(f"Veri kaynagi: {data_source_label}")
    st.caption(f"Dotabuff durumu: {dotabuff_status}")
    st.caption("Siralama mantigi: OpenDota confidence score + yerel Dotabuff worst-versus sinyali")
    render_counter_cards(results_df)

    display_df = results_df.copy()
    display_df["roles"] = display_df["roles"].apply(lambda roles: ", ".join(roles))
    display_df = display_df.rename(
        columns={
            "image_url": "Image",
            "localized_name": "Hero",
            "games_played": "Games",
            "wins": "Wins",
            "win_rate": "Win Rate (%)",
            "stabilized_win_rate": "Stabilized Win Rate (%)",
            "avg_enemy_overlap": "Avg Enemy Match Count",
            "sample_factor": "Sample Factor",
            "overlap_factor": "Overlap Factor",
            "confidence_score": "Confidence Score",
            "dotabuff_disadvantage": "Dotabuff Disadvantage (%)",
            "dotabuff_matches": "Dotabuff Matches",
            "dotabuff_enemy_hits": "Dotabuff Enemy Hits",
            "hybrid_score": "Hybrid Score",
            "roles": "Roles",
        }
    )

    st.subheader("Counter Sonuclari")
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Image": st.column_config.ImageColumn("Image", help="Hero resmi", width="medium"),
        },
    )

    chart_df = results_df.loc[:, ["localized_name", "win_rate"]].set_index("localized_name")
    st.subheader("Win Rate Grafigi")
    st.bar_chart(chart_df)


if __name__ == "__main__":
    main()
